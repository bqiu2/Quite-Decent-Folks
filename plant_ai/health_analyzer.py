from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import (
    HEALTH_LEVEL_TEMPERATURE,
    HEALTH_LEVEL_VALUES,
    HEALTH_NEUTRAL_SCORE,
    HEALTH_VISUAL_RELIABILITY,
)
from .model_loader import SigLIP2Backend, get_backend
from .prompts import HEALTH_PROMPTS


@dataclass
class DimensionResult:
    raw_score: float
    final_score: float
    confidence: float
    level_scores: list[float]


def _softmax(values: np.ndarray, temperature: float) -> np.ndarray:
    temperature = max(float(temperature), 1e-6)
    x = values.astype(np.float64) / temperature
    x -= np.max(x)
    exp = np.exp(x)
    return exp / np.sum(exp)


class PlantHealthAnalyzer:
    def __init__(self, backend: SigLIP2Backend | None = None) -> None:
        self.backend = backend or get_backend()

    def analyze(self, image) -> dict[str, DimensionResult]:
        # 把所有维度 Prompt 一次性送入模型，避免 6 次重复视觉前向。
        flat_prompts: list[str] = []
        mapping: dict[str, list[tuple[int, int]]] = {}

        for dimension, levels in HEALTH_PROMPTS.items():
            mapping[dimension] = []
            for prompts_for_level in levels:
                start = len(flat_prompts)
                flat_prompts.extend(prompts_for_level)
                end = len(flat_prompts)
                mapping[dimension].append((start, end))

        logits = self.backend.text_logits(image, flat_prompts)
        results: dict[str, DimensionResult] = {}
        level_values = np.asarray(HEALTH_LEVEL_VALUES, dtype=np.float64)

        for dimension, ranges in mapping.items():
            group_logits = np.asarray([
                float(np.mean(logits[start:end]))
                for start, end in ranges
            ], dtype=np.float64)

            level_probs = _softmax(group_logits, HEALTH_LEVEL_TEMPERATURE)
            raw_score = float(np.sum(level_probs * level_values))

            sorted_probs = np.sort(level_probs)
            margin = float(sorted_probs[-1] - sorted_probs[-2])
            entropy = -float(np.sum(level_probs * np.log(level_probs + 1e-12)))
            entropy_max = float(np.log(len(level_probs)))
            entropy_conf = 1.0 - entropy / entropy_max
            confidence = float(np.clip(0.55 * margin + 0.45 * entropy_conf, 0.0, 1.0))

            base_reliability = HEALTH_VISUAL_RELIABILITY[dimension]
            # 即使模型显得很“自信”，N/P/K 单张 RGB 图仍不应被当成化学测量。
            effective_reliability = base_reliability * (0.65 + 0.35 * confidence)

            final_score = (
                effective_reliability * raw_score
                + (1.0 - effective_reliability) * HEALTH_NEUTRAL_SCORE
            )
            final_score = float(np.clip(final_score, 0.0, 1.0))

            results[dimension] = DimensionResult(
                raw_score=round(raw_score, 4),
                final_score=round(final_score, 4),
                confidence=round(confidence, 4),
                level_scores=[round(float(x), 4) for x in level_probs],
            )

        return results


_HEALTH_ANALYZER: PlantHealthAnalyzer | None = None


def get_health_analyzer() -> PlantHealthAnalyzer:
    global _HEALTH_ANALYZER
    if _HEALTH_ANALYZER is None:
        _HEALTH_ANALYZER = PlantHealthAnalyzer()
    return _HEALTH_ANALYZER
