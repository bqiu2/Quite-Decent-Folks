from __future__ import annotations

from typing import Iterable

import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

from .config import MODEL_NAME


class SigLIP2Backend:
    """只加载一次 SigLIP2，并提供图像特征与图文相似度接口。"""

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[PlantAI] loading {MODEL_NAME} on {self.device} ...")

        self.processor = AutoProcessor.from_pretrained(MODEL_NAME)
        self.model = AutoModel.from_pretrained(MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()

        print("[PlantAI] model ready.")

    @staticmethod
    def _extract_feature_tensor(features) -> torch.Tensor:
        """兼容不同 Transformers 版本中 get_image_features 的返回形式。"""
        if torch.is_tensor(features):
            return features

        pooler = getattr(features, "pooler_output", None)
        if pooler is not None:
            return pooler

        image_embeds = getattr(features, "image_embeds", None)
        if image_embeds is not None:
            return image_embeds

        if isinstance(features, (tuple, list)) and features:
            first = features[0]
            if torch.is_tensor(first):
                return first

        raise TypeError(
            "Unsupported get_image_features() return type: "
            f"{type(features)!r}"
        )

    @torch.inference_mode()
    def encode_images(self, images: Iterable[Image.Image]) -> np.ndarray:
        image_list = [img.convert("RGB") for img in images]
        if not image_list:
            raise ValueError("encode_images() received an empty image list")

        inputs = self.processor(images=image_list, return_tensors="pt")
        inputs = inputs.to(self.device)

        features = self.model.get_image_features(**inputs)
        features = self._extract_feature_tensor(features)
        features = features.float()
        features = features / features.norm(p=2, dim=-1, keepdim=True).clamp_min(1e-12)
        return features.cpu().numpy()

    @torch.inference_mode()
    def text_logits(self, image: Image.Image, descriptions: list[str]) -> np.ndarray:
        """返回同一张图片与多条文本的 SigLIP2 原始 logits。"""
        if not descriptions:
            raise ValueError("descriptions cannot be empty")

        # 官方 zero-shot 示例使用 This is a photo of ... 模板。
        texts = [f"This is a photo of {text}." for text in descriptions]

        inputs = self.processor(
            text=texts,
            images=image.convert("RGB"),
            padding="max_length",
            truncation=True,
            max_length=64,
            return_tensors="pt",
        )
        inputs = inputs.to(self.device)
        outputs = self.model(**inputs)
        return outputs.logits_per_image[0].float().cpu().numpy()

    def text_sigmoid_scores(self, image: Image.Image, descriptions: list[str]) -> np.ndarray:
        logits = self.text_logits(image, descriptions)
        # SigLIP/SigLIP2 对每个图文配对采用 sigmoid，而不是要求所有候选总和为 1。
        return 1.0 / (1.0 + np.exp(-np.clip(logits, -40.0, 40.0)))


_BACKEND: SigLIP2Backend | None = None


def get_backend() -> SigLIP2Backend:
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = SigLIP2Backend()
    return _BACKEND
