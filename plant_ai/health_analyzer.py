"""
plant_ai/health_analyzer.py

BioCLIP 六维植物状态分析。

严格遵循 shared_game_data.py：

    water
    light
    nitrogen
    phosphorus
    potassium
    pest

统一规则：
    1. 全部为 0.0 ~ 1.0
    2. 全部越高越健康
    3. water/light/N/P/K 最低 0.37
    4. pest 最低 0.73
    5. 六维最终结果加入微小随机抖动 ±0.01
    6. 抖动后仍严格遵守上述上下限

BioCLIP 这里只判断 RGB 图片中的可见症状，
不等价于实验室营养元素测定。
"""

from __future__ import annotations

import random
import threading
from typing import Any

import torch

from shared_game_data import (
    PlantStatus,
    normalize_plant_status,
)

from .image_preprocess import load_rgb_image
from .model_loader import get_bioclip


# ============================================================
# 游戏平衡参数
# ============================================================

# water / light / N / P / K 最低值
BASIC_STATUS_FLOOR = 0.37

# pest 最低值
PEST_STATUS_FLOOR = 0.73

# 六维随机抖动幅度：
#
# 最终数值会加入：
#     random.uniform(-0.01, +0.01)
#
# 也就是最多上下浮动 1 个百分点。
JITTER_AMPLITUDE = 0.03

BASIC_DIMENSIONS = (
    "water",
    "light",
    "nitrogen",
    "phosphorus",
    "potassium",
)


# ============================================================
# BioCLIP 六维 prompts
# ============================================================

HEALTH_PROMPTS = {
    "water": {
        "normal": [
            "a healthy well-watered plant with firm upright leaves",
            "a hydrated healthy plant with normal leaf turgor",
            "a healthy plant with fresh firm green foliage",
            "a plant showing no visible water stress",
        ],
        "stress": [
            "a water-stressed plant with wilted drooping leaves",
            "a dehydrated plant with limp dry leaves",
            "a drought-stressed plant with curled wilting foliage",
            "a plant showing visible water stress and loss of leaf turgor",
            "an overwatered stressed plant with yellow drooping leaves",
        ],
    },

    "light": {
        "normal": [
            "a healthy plant receiving appropriate light",
            "a compact healthy plant with normal green leaves and normal growth",
            "a normally illuminated healthy plant",
            "a healthy plant showing no visible light stress",
        ],
        "stress": [
            "an etiolated plant with elongated weak stems caused by insufficient light",
            "a pale plant stretching toward light",
            "a plant suffering from insufficient light with weak elongated growth",
            "a plant with sun-scorched bleached leaves from excessive light",
            "a plant showing leaf scorch caused by intense sunlight",
        ],
    },

    "nitrogen": {
        "normal": [
            "a healthy plant with adequate nitrogen nutrition",
            "a plant with healthy green foliage and normal nitrogen status",
            "a vigorous healthy plant with normal green leaves",
            "a plant showing no visible nitrogen deficiency",
        ],
        "stress": [
            "a nitrogen deficient plant with generalized leaf chlorosis",
            "a nitrogen deficient plant with pale yellow older leaves",
            "a plant suffering from nitrogen deficiency with reduced green coloration",
            "a nitrogen-starved plant with yellowing foliage and weak growth",
        ],
    },

    "phosphorus": {
        "normal": [
            "a healthy plant with adequate phosphorus nutrition",
            "a plant showing normal healthy growth and phosphorus status",
            "a healthy plant with normal green foliage and normal development",
            "a plant showing no visible phosphorus deficiency",
        ],
        "stress": [
            "a phosphorus deficient plant with stunted growth",
            "a plant suffering from phosphorus deficiency with dark green foliage",
            "a phosphorus deficient plant with purplish leaf coloration",
            "a plant showing visible symptoms of phosphorus deficiency",
        ],
    },

    "potassium": {
        "normal": [
            "a healthy plant with adequate potassium nutrition",
            "a plant with healthy intact leaf margins and normal potassium status",
            "a healthy plant with normal green foliage and strong growth",
            "a plant showing no visible potassium deficiency",
        ],
        "stress": [
            "a potassium deficient plant with marginal leaf chlorosis",
            "a potassium deficient plant with scorched brown leaf edges",
            "a plant suffering from potassium deficiency with marginal leaf necrosis",
            "a plant showing visible potassium deficiency symptoms on leaf margins",
        ],
    },

    "pest": {
        "normal": [
            "a healthy plant with intact leaves and no visible pests",
            "clean healthy foliage without insect feeding damage",
            "a plant with undamaged leaves and no visible insects",
            "healthy intact plant leaves without pest damage",
            "a healthy plant free from insect infestation",
        ],
        "stress": [
            "a plant damaged by insects",
            "plant leaves with visible insect feeding damage",
            "leaves with holes caused by pests",
            "a plant with visible insects or insect eggs on the leaves",
            "plant foliage showing chewing damage and pest infestation",
        ],
    },
}


class HealthAnalyzer:
    """
    BioCLIP 六维植物状态分析器。
    """

    def __init__(
        self,
        device: str | None = None,
    ):
        bundle = get_bioclip(
            device=device
        )

        self.model: Any = bundle.model
        self.preprocess: Any = bundle.preprocess
        self.tokenizer: Any = bundle.tokenizer
        self.device = bundle.device

        self.text_features = (
            self._build_text_features()
        )

    @torch.inference_mode()
    def _mean_text_feature(
        self,
        prompts: list[str],
    ):
        tokens = self.tokenizer(
            prompts
        ).to(self.device)

        features = self.model.encode_text(
            tokens
        )

        features = (
            features
            / features.norm(
                dim=-1,
                keepdim=True,
            ).clamp_min(1e-12)
        )

        feature = features.mean(
            dim=0
        )

        return (
            feature
            / feature.norm().clamp_min(1e-12)
        )

    @torch.inference_mode()
    def _build_text_features(self):
        result = {}

        for (
            dimension,
            prompts,
        ) in HEALTH_PROMPTS.items():

            normal_feature = (
                self._mean_text_feature(
                    prompts["normal"]
                )
            )

            stress_feature = (
                self._mean_text_feature(
                    prompts["stress"]
                )
            )

            result[dimension] = torch.stack(
                [
                    normal_feature,
                    stress_feature,
                ],
                dim=0,
            )

        return result

    def _get_logit_scale(
        self,
        dtype,
    ):
        if hasattr(
            self.model,
            "logit_scale",
        ):
            return torch.clamp(
                self.model.logit_scale.exp().detach(),
                max=100.0,
            )

        return torch.tensor(
            100.0,
            device=self.device,
            dtype=dtype,
        )

    @staticmethod
    def _get_floor(
        dimension: str,
    ) -> float:
        """
        获取各维度最低允许值。
        """

        if dimension == "pest":
            return PEST_STATUS_FLOOR

        return BASIC_STATUS_FLOOR

    @staticmethod
    def _apply_game_floor(
        dimension: str,
        raw_healthy_score: float,
    ) -> float:
        """
        第一步：
        应用游戏最低值，但暂时不加随机抖动。
        """

        score = max(
            0.0,
            min(
                1.0,
                raw_healthy_score,
            ),
        )

        floor = HealthAnalyzer._get_floor(
            dimension
        )

        score = max(
            floor,
            score,
        )

        return score

    @staticmethod
    def _apply_jitter(
        dimension: str,
        value: float,
    ) -> tuple[float, float]:
        """
        第二步：
        给最终状态加入独立随机抖动。

        返回：
            (抖动后的值, 本次随机抖动量)

        例如：
            value = 0.62
            jitter = -0.006
            final = 0.614

        抖动之后再次 clamp：
            water/light/N/P/K >= 0.37
            pest >= 0.73
            所有值 <= 1.0
        """

        jitter = random.uniform(
            -JITTER_AMPLITUDE,
            JITTER_AMPLITUDE,
        )

        floor = HealthAnalyzer._get_floor(
            dimension
        )

        jittered_value = (
            value
            + jitter
        )

        jittered_value = max(
            floor,
            min(
                1.0,
                jittered_value,
            ),
        )

        return (
            round(
                jittered_value,
                4,
            ),
            round(
                jitter,
                4,
            ),
        )

    @torch.inference_mode()
    def _extract_image_feature(
        self,
        image,
    ):
        pil_image = load_rgb_image(
            image
        )

        image_tensor = (
            self.preprocess(
                pil_image
            )
            .unsqueeze(0)
            .to(self.device)
        )

        image_feature = (
            self.model.encode_image(
                image_tensor
            )
        )

        return (
            image_feature
            / image_feature.norm(
                dim=-1,
                keepdim=True,
            ).clamp_min(1e-12)
        )

    @torch.inference_mode()
    def analyze_debug(
        self,
        image,
    ) -> dict:
        """
        返回详细 BioCLIP 调试结果。

        value:
            最终传给游戏的值，已经包含随机抖动。

        value_before_jitter:
            应用最低值以后、随机抖动以前的值。

        jitter:
            本次实际加入的随机量。
        """

        image_feature = (
            self._extract_image_feature(
                image
            )
        )

        scale = self._get_logit_scale(
            image_feature.dtype
        )

        debug = {}

        for (
            dimension,
            text_features,
        ) in self.text_features.items():

            similarities = (
                image_feature
                @ text_features.T
            )[0]

            probabilities = torch.softmax(
                similarities * scale,
                dim=-1,
            )

            healthy_probability = float(
                probabilities[0].item()
            )

            stress_probability = float(
                probabilities[1].item()
            )

            # 先应用游戏下限
            value_before_jitter = (
                self._apply_game_floor(
                    dimension,
                    healthy_probability,
                )
            )

            # 再加微小随机抖动
            final_value, jitter = (
                self._apply_jitter(
                    dimension,
                    value_before_jitter,
                )
            )

            confidence = abs(
                healthy_probability
                - stress_probability
            )

            debug[dimension] = {
                "value": final_value,

                "value_before_jitter": round(
                    value_before_jitter,
                    4,
                ),

                "jitter": jitter,

                "raw_healthy_probability": round(
                    healthy_probability,
                    4,
                ),

                "raw_stress_probability": round(
                    stress_probability,
                    4,
                ),

                "confidence": round(
                    confidence,
                    4,
                ),

                "similarity_healthy": round(
                    float(
                        similarities[0].item()
                    ),
                    6,
                ),

                "similarity_stress": round(
                    float(
                        similarities[1].item()
                    ),
                    6,
                ),
            }

        return debug

    @torch.inference_mode()
    def analyze(
        self,
        image,
    ) -> PlantStatus:
        """
        正式游戏接口。

        返回 shared_game_data.PlantStatus。
        六个值均已经加入随机抖动。
        """

        debug = self.analyze_debug(
            image
        )

        status = PlantStatus(
            water=debug["water"]["value"],
            light=debug["light"]["value"],
            nitrogen=debug["nitrogen"]["value"],
            phosphorus=debug["phosphorus"]["value"],
            potassium=debug["potassium"]["value"],
            pest=debug["pest"]["value"],
        )

        return normalize_plant_status(
            status
        )

    def score(
        self,
        image,
    ) -> dict[str, float]:
        """
        返回六维简单字典。
        """

        status = self.analyze(
            image
        )

        return {
            "water": status.water,
            "light": status.light,
            "nitrogen": status.nitrogen,
            "phosphorus": status.phosphorus,
            "potassium": status.potassium,
            "pest": status.pest,
        }


_HEALTH_ANALYZERS: dict[str, HealthAnalyzer] = {}
_HEALTH_ANALYZER_LOCK = threading.Lock()


def get_health_analyzer(
    device: str | None = None,
) -> HealthAnalyzer:
    key = str(device or "default")
    with _HEALTH_ANALYZER_LOCK:
        analyzer = _HEALTH_ANALYZERS.get(key)
        if analyzer is None:
            analyzer = HealthAnalyzer(device=device)
            _HEALTH_ANALYZERS[key] = analyzer
        return analyzer


def analyze_health(
    image,
    device: str | None = None,
) -> PlantStatus:
    """
    正式接口：
    返回 PlantStatus。
    """

    return get_health_analyzer(
        device=device
    ).analyze(image)


def analyze_health_debug(
    image,
    device: str | None = None,
) -> dict:
    """
    调试接口：
    返回原始概率、下限处理、随机抖动和最终结果。
    """

    return get_health_analyzer(
        device=device
    ).analyze_debug(image)


def get_health_scores(
    image,
    device: str | None = None,
) -> dict[str, float]:
    return get_health_analyzer(
        device=device
    ).score(image)
