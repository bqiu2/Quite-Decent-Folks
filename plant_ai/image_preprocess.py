from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .config import (
    AUTO_CROP_ENABLED,
    CROP_PADDING_RATIO,
    MIN_CROP_AREA_RATIO,
    MIN_VEGETATION_COVERAGE,
)


@dataclass
class CropResult:
    image: Image.Image
    bbox: tuple[int, int, int, int]
    vegetation_coverage: float
    used_auto_crop: bool


def load_rgb_image(image_path: str | Path) -> Image.Image:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Plant image not found: {path}")

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB").copy()


def _vegetation_mask(rgb: np.ndarray) -> np.ndarray:
    """用 HSV + Excess Green 得到一个轻量植物候选区域，不额外引入分割模型。"""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)

    # OpenCV H 范围为 0~179。这里覆盖黄绿到深绿色叶片。
    hsv_mask = (
        (h >= 14)
        & (h <= 105)
        & (s >= 28)
        & (v >= 25)
    )

    arr = rgb.astype(np.int16)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    exg = 2 * g - r - b
    exg_mask = (exg >= 12) & (g >= 35)

    mask = (hsv_mask | exg_mask).astype(np.uint8) * 255

    kernel_small = np.ones((3, 3), np.uint8)
    kernel_large = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_large)
    return mask


def auto_crop_plant(image: Image.Image) -> CropResult:
    image = image.convert("RGB")
    width, height = image.size
    full_bbox = (0, 0, width, height)

    if not AUTO_CROP_ENABLED or width < 80 or height < 80:
        return CropResult(image, full_bbox, 0.0, False)

    rgb = np.asarray(image)
    mask = _vegetation_mask(rgb)
    coverage = float(np.count_nonzero(mask)) / float(mask.size)

    if coverage < MIN_VEGETATION_COVERAGE:
        return CropResult(image, full_bbox, coverage, False)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_component_area = max(20, int(mask.size * 0.0015))

    boxes: list[tuple[int, int, int, int]] = []
    for label in range(1, n_labels):
        x, y, w, h, area = stats[label]
        if area >= min_component_area:
            boxes.append((int(x), int(y), int(x + w), int(y + h)))

    if not boxes:
        return CropResult(image, full_bbox, coverage, False)

    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes)
    y2 = max(b[3] for b in boxes)

    pad_x = int((x2 - x1) * CROP_PADDING_RATIO)
    pad_y = int((y2 - y1) * CROP_PADDING_RATIO)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(width, x2 + pad_x)
    y2 = min(height, y2 + pad_y)

    crop_area_ratio = ((x2 - x1) * (y2 - y1)) / float(width * height)
    if crop_area_ratio < MIN_CROP_AREA_RATIO:
        # 候选框太小通常代表只找到了背景中的一小块绿色，不要贸然裁剪。
        return CropResult(image, full_bbox, coverage, False)

    cropped = image.crop((x1, y1, x2, y2))
    return CropResult(cropped, (x1, y1, x2, y2), coverage, True)


def save_debug_crop(crop: CropResult, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.image.save(out)
