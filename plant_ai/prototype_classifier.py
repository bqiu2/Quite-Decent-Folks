from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

import numpy as np

from .config import (
    FLOWER_PRESENCE_THRESHOLD,
    FLOWER_PROTOTYPE_MARGIN,
    FLOWER_STRONG_THRESHOLD,
    MIN_REFERENCE_IMAGES_PER_CLASS,
    PLANT_TYPES,
    PROTOTYPE_CACHE,
    REFERENCE_BATCH_SIZE,
    REFERENCE_DIR,
    SUPPORTED_IMAGE_SUFFIXES,
    TYPE_SOFTMAX_TEMPERATURE,
)
from .image_preprocess import auto_crop_plant, load_rgb_image
from .model_loader import SigLIP2Backend, get_backend
from .prompts import (
    FLOWER_NEGATIVE_PROMPTS,
    FLOWER_POSITIVE_PROMPTS,
    TYPE_FALLBACK_PROMPTS,
)


@dataclass
class TypeClassificationResult:
    plant_type: str
    method: str
    scores: dict[str, float]
    similarities: dict[str, float] = field(default_factory=dict)
    flower_presence: float = 0.0
    reference_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _softmax(values: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    temperature = max(float(temperature), 1e-6)
    x = values.astype(np.float64) / temperature
    x -= np.max(x)
    exp = np.exp(x)
    return exp / np.sum(exp)


class PrototypePlantClassifier:
    def __init__(self, backend: SigLIP2Backend | None = None) -> None:
        self.backend = backend or get_backend()

    def _reference_files(self) -> dict[str, list[Path]]:
        result: dict[str, list[Path]] = {}
        for class_name in PLANT_TYPES:
            folder = REFERENCE_DIR / class_name
            folder.mkdir(parents=True, exist_ok=True)
            files = sorted(
                p for p in folder.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
            )
            result[class_name] = files
        return result

    def reference_counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self._reference_files().items()}

    def _manifest(self, files_by_class: dict[str, list[Path]]) -> str:
        hasher = sha256()
        for class_name in PLANT_TYPES:
            for path in files_by_class[class_name]:
                stat = path.stat()
                record = f"{class_name}|{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}\n"
                hasher.update(record.encode("utf-8"))
        return hasher.hexdigest()

    def _references_ready(self, counts: dict[str, int]) -> bool:
        return all(counts[name] >= MIN_REFERENCE_IMAGES_PER_CLASS for name in PLANT_TYPES)

    def rebuild_cache(self, force: bool = True) -> dict[str, int]:
        files_by_class = self._reference_files()
        counts = {k: len(v) for k, v in files_by_class.items()}

        if not self._references_ready(counts):
            raise RuntimeError(
                "Reference images are incomplete. Need at least "
                f"{MIN_REFERENCE_IMAGES_PER_CLASS} images in every class. "
                f"Current counts: {counts}"
            )

        manifest = self._manifest(files_by_class)
        if PROTOTYPE_CACHE.exists() and not force:
            try:
                cached = np.load(PROTOTYPE_CACHE, allow_pickle=False)
                if str(cached["manifest"].item()) == manifest:
                    return counts
            except Exception:
                pass

        PROTOTYPE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        prototypes: dict[str, np.ndarray] = {}

        for class_name in PLANT_TYPES:
            paths = files_by_class[class_name]
            all_features: list[np.ndarray] = []
            print(f"[PlantAI] building {class_name} prototype from {len(paths)} images ...")

            for start in range(0, len(paths), REFERENCE_BATCH_SIZE):
                batch_paths = paths[start:start + REFERENCE_BATCH_SIZE]
                batch_images = []
                for path in batch_paths:
                    image = load_rgb_image(path)
                    crop = auto_crop_plant(image)
                    batch_images.append(crop.image)

                features = self.backend.encode_images(batch_images)
                all_features.append(features)

            matrix = np.concatenate(all_features, axis=0)
            prototype = matrix.mean(axis=0)
            prototype /= max(np.linalg.norm(prototype), 1e-12)
            prototypes[class_name] = prototype.astype(np.float32)

        np.savez_compressed(
            PROTOTYPE_CACHE,
            manifest=np.array(manifest),
            grass=prototypes["grass"],
            shrub=prototypes["shrub"],
            flower=prototypes["flower"],
        )
        print(f"[PlantAI] prototype cache saved: {PROTOTYPE_CACHE}")
        return counts

    def _load_or_build_prototypes(self) -> tuple[dict[str, np.ndarray] | None, dict[str, int]]:
        files_by_class = self._reference_files()
        counts = {k: len(v) for k, v in files_by_class.items()}
        if not self._references_ready(counts):
            return None, counts

        manifest = self._manifest(files_by_class)
        cache_ok = False
        if PROTOTYPE_CACHE.exists():
            try:
                cached = np.load(PROTOTYPE_CACHE, allow_pickle=False)
                cache_ok = str(cached["manifest"].item()) == manifest
            except Exception:
                cache_ok = False

        if not cache_ok:
            self.rebuild_cache(force=True)

        cached = np.load(PROTOTYPE_CACHE, allow_pickle=False)
        prototypes = {
            class_name: cached[class_name].astype(np.float32)
            for class_name in PLANT_TYPES
        }
        return prototypes, counts

    def _flower_presence(self, image) -> float:
        descriptions = FLOWER_POSITIVE_PROMPTS + FLOWER_NEGATIVE_PROMPTS
        logits = self.backend.text_logits(image, descriptions)
        n_pos = len(FLOWER_POSITIVE_PROMPTS)
        pos_logit = float(np.mean(logits[:n_pos]))
        neg_logit = float(np.mean(logits[n_pos:]))
        relative = _softmax(np.array([neg_logit, pos_logit]), temperature=1.0)
        return float(relative[1])

    def _fallback_classify(self, image, flower_presence: float, counts: dict[str, int]) -> TypeClassificationResult:
        warnings = [
            "Prototype reference images are incomplete; using prompt fallback. "
            "For better type accuracy, add reference images for grass/shrub/flower."
        ]

        flat_prompts: list[str] = []
        groups: list[tuple[str, int, int]] = []
        for class_name in ("grass", "shrub"):
            start = len(flat_prompts)
            flat_prompts.extend(TYPE_FALLBACK_PROMPTS[class_name])
            groups.append((class_name, start, len(flat_prompts)))

        logits = self.backend.text_logits(image, flat_prompts)
        class_logits = []
        for class_name, start, end in groups:
            class_logits.append(float(np.mean(logits[start:end])))

        nonflower_probs = _softmax(np.asarray(class_logits), temperature=1.0)
        grass_score = float(nonflower_probs[0]) * (1.0 - flower_presence)
        shrub_score = float(nonflower_probs[1]) * (1.0 - flower_presence)
        flower_score = flower_presence

        if flower_presence >= FLOWER_STRONG_THRESHOLD:
            plant_type = "flower"
        else:
            plant_type = "grass" if nonflower_probs[0] >= nonflower_probs[1] else "shrub"

        total = grass_score + shrub_score + flower_score
        scores = {
            "grass": grass_score / total,
            "shrub": shrub_score / total,
            "flower": flower_score / total,
        }
        return TypeClassificationResult(
            plant_type=plant_type,
            method="prompt_fallback",
            scores=scores,
            flower_presence=flower_presence,
            reference_counts=counts,
            warnings=warnings,
        )

    def classify(self, image) -> TypeClassificationResult:
        prototypes, counts = self._load_or_build_prototypes()
        flower_presence = self._flower_presence(image)

        if prototypes is None:
            return self._fallback_classify(image, flower_presence, counts)

        image_feature = self.backend.encode_images([image])[0]
        similarities = {
            class_name: float(np.dot(image_feature, prototypes[class_name]))
            for class_name in PLANT_TYPES
        }
        sim_array = np.asarray([similarities[name] for name in PLANT_TYPES], dtype=np.float64)
        probs = _softmax(sim_array, temperature=TYPE_SOFTMAX_TEMPERATURE)
        scores = {name: float(probs[i]) for i, name in enumerate(PLANT_TYPES)}

        nonflower_type = "grass" if similarities["grass"] >= similarities["shrub"] else "shrub"
        nonflower_best_sim = max(similarities["grass"], similarities["shrub"])
        flower_margin = similarities["flower"] - nonflower_best_sim
        raw_best = max(PLANT_TYPES, key=lambda name: similarities[name])

        # 关键修正：flower 必须同时满足“原型像 flower”与“确实看得到花”。
        if (
            raw_best == "flower"
            and flower_presence >= FLOWER_PRESENCE_THRESHOLD
            and flower_margin >= FLOWER_PROTOTYPE_MARGIN
        ):
            plant_type = "flower"
        elif (
            flower_presence >= FLOWER_STRONG_THRESHOLD
            and similarities["flower"] >= nonflower_best_sim - 0.008
        ):
            plant_type = "flower"
        else:
            plant_type = nonflower_type

        warnings: list[str] = []
        if min(counts.values()) < 15:
            warnings.append(
                f"Only {counts} reference images are available. "
                "15~30 per class is recommended for a more stable prototype."
            )

        return TypeClassificationResult(
            plant_type=plant_type,
            method="image_prototype",
            scores=scores,
            similarities=similarities,
            flower_presence=flower_presence,
            reference_counts=counts,
            warnings=warnings,
        )


_CLASSIFIER: PrototypePlantClassifier | None = None


def get_type_classifier() -> PrototypePlantClassifier:
    global _CLASSIFIER
    if _CLASSIFIER is None:
        _CLASSIFIER = PrototypePlantClassifier()
    return _CLASSIFIER
