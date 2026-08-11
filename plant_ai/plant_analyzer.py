from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from shared_game_data import (
    PlantData,
    PlantStatus,
    calculate_power,
    normalize_plant_status,
)

from .config import DATA_DIR, PLANT_ID_COUNTER
from .health_analyzer import get_health_analyzer
from .image_preprocess import auto_crop_plant, load_rgb_image, save_debug_crop
from .prototype_classifier import get_type_classifier


@dataclass
class PlantAnalysisDetails:
    plant_type: str
    type_method: str
    type_scores: dict[str, float]
    type_similarities: dict[str, float]
    flower_presence: float
    reference_counts: dict[str, int]
    crop_bbox: tuple[int, int, int, int]
    crop_vegetation_coverage: float
    crop_used: bool
    health_raw_scores: dict[str, float]
    health_final_scores: dict[str, float]
    health_confidence: dict[str, float]
    health_level_scores: dict[str, list[float]]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _generate_plant_id() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    current = 0
    if PLANT_ID_COUNTER.exists():
        try:
            current = int(PLANT_ID_COUNTER.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            current = 0

    current += 1
    PLANT_ID_COUNTER.write_text(str(current), encoding="utf-8")
    return f"PLANT_{current:04d}"


def analyze_plant_with_details(
    image_path: str,
    *,
    debug_crop_path: str | None = None,
) -> tuple[PlantData, PlantAnalysisDetails]:
    image_path_obj = Path(image_path)
    original = load_rgb_image(image_path_obj)
    crop = auto_crop_plant(original)

    if debug_crop_path:
        save_debug_crop(crop, debug_crop_path)

    classifier = get_type_classifier()
    type_result = classifier.classify(crop.image)

    health_analyzer = get_health_analyzer()
    health = health_analyzer.analyze(crop.image)

    status = PlantStatus(
        water=health["water"].final_score,
        light=health["light"].final_score,
        nitrogen=health["nitrogen"].final_score,
        phosphorus=health["phosphorus"].final_score,
        potassium=health["potassium"].final_score,
        pest=health["pest"].final_score,
    )
    status = normalize_plant_status(status)
    power = calculate_power(status)

    plant = PlantData(
        plant_id=_generate_plant_id(),
        plant_type=type_result.plant_type,
        image_path=str(image_path_obj),
        status=status,
        initial_power=power,
        current_power=power,
    )

    warnings = list(type_result.warnings)
    warnings.append(
        "water/pest are visual estimates; light/N/P/K are visible-symptom estimates, "
        "not direct physical or chemical measurements."
    )

    details = PlantAnalysisDetails(
        plant_type=type_result.plant_type,
        type_method=type_result.method,
        type_scores={k: round(v, 4) for k, v in type_result.scores.items()},
        type_similarities={k: round(v, 4) for k, v in type_result.similarities.items()},
        flower_presence=round(type_result.flower_presence, 4),
        reference_counts=type_result.reference_counts,
        crop_bbox=crop.bbox,
        crop_vegetation_coverage=round(crop.vegetation_coverage, 4),
        crop_used=crop.used_auto_crop,
        health_raw_scores={k: v.raw_score for k, v in health.items()},
        health_final_scores={k: v.final_score for k, v in health.items()},
        health_confidence={k: v.confidence for k, v in health.items()},
        health_level_scores={k: v.level_scores for k, v in health.items()},
        warnings=warnings,
    )

    return plant, details


def analyze_plant(image_path: str) -> PlantData:
    """统一给游戏调用的接口：图片 -> PlantData。"""
    plant, _ = analyze_plant_with_details(image_path)
    return plant
