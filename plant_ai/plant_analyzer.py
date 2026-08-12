"""
plant_ai/plant_analyzer.py

BioCLIP 植物类型分类 + shared_game_data.PlantData 统一输出。

正式游戏接口：

    plant = analyze_plant("image.jpg")

返回：
    shared_game_data.PlantData

其中：
    plant.status        -> PlantStatus
    plant.initial_power -> calculate_power(status)
    plant.current_power -> 初始时等于 initial_power
"""

from __future__ import annotations

from pathlib import Path
import threading

import torch

from shared_game_data import (
    PlantData,
    calculate_power,
)

from .config import (
    MODEL_NAME,
    PLANT_TYPES,
    PLANT_TYPE_TO_ID,
)
from .prompts import CLASS_PROMPTS
from .model_loader import get_bioclip
from .image_preprocess import load_rgb_image
from .health_analyzer import analyze_health


class PlantAnalyzer:
    """
    BioCLIP grass / shrub / flower 分类器。
    """

    def __init__(self, device=None):
        bundle = get_bioclip(device=device)

        self.model = bundle.model
        self.preprocess = bundle.preprocess
        self.tokenizer = bundle.tokenizer
        self.device = bundle.device

        self.text_features = self._build_text_features()

    @torch.inference_mode()
    def _build_text_features(self):
        class_features = []

        for plant_type in PLANT_TYPES:
            prompts = CLASS_PROMPTS[plant_type]

            tokens = self.tokenizer(
                prompts
            ).to(self.device)

            features = self.model.encode_text(tokens)

            features = features / features.norm(
                dim=-1,
                keepdim=True,
            ).clamp_min(1e-12)

            feature = features.mean(dim=0)

            feature = feature / feature.norm().clamp_min(
                1e-12
            )

            class_features.append(feature)

        return torch.stack(
            class_features,
            dim=0,
        )

    @torch.inference_mode()
    def classify(self, image):
        """
        返回类型分类调试字典。
        这个接口保留给测试使用。
        """

        pil_image = load_rgb_image(image)

        image_tensor = self.preprocess(
            pil_image
        ).unsqueeze(0).to(self.device)

        image_features = self.model.encode_image(
            image_tensor
        )

        image_features = image_features / image_features.norm(
            dim=-1,
            keepdim=True,
        ).clamp_min(1e-12)

        similarities = (
            image_features @ self.text_features.T
        )[0]

        if hasattr(self.model, "logit_scale"):
            scale = torch.clamp(
                self.model.logit_scale.exp().detach(),
                max=100.0,
            )
        else:
            scale = torch.tensor(
                100.0,
                device=self.device,
                dtype=similarities.dtype,
            )

        probabilities = torch.softmax(
            similarities * scale,
            dim=-1,
        )

        best_index = int(
            probabilities.argmax().item()
        )

        plant_type = PLANT_TYPES[
            best_index
        ]

        sorted_probabilities, _ = torch.sort(
            probabilities,
            descending=True,
        )

        margin = float(
            (
                sorted_probabilities[0]
                - sorted_probabilities[1]
            ).item()
        )

        return {
            "plant_type": plant_type,
            # 注意：
            # 这是分类调试 ID，不是 PlantData.plant_id。
            "type_id": PLANT_TYPE_TO_ID[
                plant_type
            ],
            "confidence": float(
                probabilities[best_index].item()
            ),
            "margin": margin,
            "scores": {
                name: float(probabilities[i].item())
                for i, name in enumerate(PLANT_TYPES)
            },
            "similarities": {
                name: float(similarities[i].item())
                for i, name in enumerate(PLANT_TYPES)
            },
            "model": MODEL_NAME.replace(
                "hf-hub:",
                "",
            ),
        }


_ANALYZERS: dict[str, PlantAnalyzer] = {}
_ANALYZER_LOCK = threading.Lock()
_COUNTER_PATH = Path(__file__).resolve().parents[1] / "data" / "plant_id_counter.txt"
_FALLBACK_COUNTER = 0
_COUNTER_LOCK = threading.Lock()

# 当前进程内简单生成：
# PLANT_0001, PLANT_0002, ...
def get_plant_analyzer(device=None):
    key = str(device or "default")
    with _ANALYZER_LOCK:
        analyzer = _ANALYZERS.get(key)
        if analyzer is None:
            analyzer = PlantAnalyzer(device=device)
            _ANALYZERS[key] = analyzer
        return analyzer


def classify_plant(image, device=None):
    """
    调试接口：
    只做 grass / shrub / flower 分类，返回 dict。
    """
    return get_plant_analyzer(
        device=device
    ).classify(image)


def _new_plant_id() -> str:
    """Allocate a plant ID that remains unique across application launches."""
    global _FALLBACK_COUNTER

    with _COUNTER_LOCK:
        try:
            # The file stores the next available number, so the checked-in
            # initial value ``1`` produces the first ID ``PLANT_0001``.
            current = int(_COUNTER_PATH.read_text(encoding="utf-8").strip() or "1")
        except (OSError, ValueError):
            current = max(1, _FALLBACK_COUNTER + 1)

        next_value = max(1, current, _FALLBACK_COUNTER + 1)
        try:
            _COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = _COUNTER_PATH.with_suffix(".tmp")
            temporary_path.write_text(str(next_value + 1), encoding="utf-8")
            temporary_path.replace(_COUNTER_PATH)
        except OSError:
            # A read-only installation can still run; uniqueness is retained
            # for the lifetime of this process via the fallback counter.
            pass
        _FALLBACK_COUNTER = next_value

    return f"PLANT_{next_value:04d}"


def analyze_plant(
    image_path: str,
    device=None,
) -> PlantData:
    """
    【正式游戏统一接口】

    完全遵循 shared_game_data.py：

        def analyze_plant(image_path: str) -> PlantData

    执行：
        1. BioCLIP 判断 grass / shrub / flower
        2. BioCLIP 得到 PlantStatus 六维状态
        3. shared_game_data.calculate_power() 计算初始战力
        4. 返回 PlantData

    初次分析保证：
        initial_power == current_power
    """

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Image not found: {path}"
        )

    type_result = classify_plant(
        path,
        device=device,
    )

    status = analyze_health(
        path,
        device=device,
    )

    power = calculate_power(status)

    return PlantData(
        plant_id=_new_plant_id(),
        plant_type=type_result["plant_type"],
        image_path=str(path),
        status=status,
        initial_power=power,
        current_power=power,
    )
