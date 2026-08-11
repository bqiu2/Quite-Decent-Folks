"""
plant_ai/image_preprocess.py

统一把路径 / PIL Image / numpy.ndarray 转换成 RGB PIL Image。
"""

from pathlib import Path

import numpy as np
from PIL import Image


def load_rgb_image(image):
    """
    Parameters
    ----------
    image:
        str / pathlib.Path / PIL.Image.Image / numpy.ndarray

    Returns
    -------
    PIL.Image.Image
        RGB 图像
    """

    if isinstance(image, (str, Path)):
        image_path = Path(image)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        return Image.open(image_path).convert("RGB")

    if isinstance(image, Image.Image):
        return image.convert("RGB")

    if isinstance(image, np.ndarray):
        array = image

        if array.ndim == 2:
            return Image.fromarray(array).convert("RGB")

        if array.ndim == 3:
            # OpenCV 图像通常是 BGR。
            # 这里不擅自交换通道，因为 numpy 输入也可能本身就是 RGB。
            # 如果来源是 cv2，请在调用前先 cv2.cvtColor(..., cv2.COLOR_BGR2RGB)。
            return Image.fromarray(array).convert("RGB")

        raise ValueError(
            f"Unsupported numpy image shape: {array.shape}"
        )

    raise TypeError(
        "image must be a path, PIL.Image.Image, or numpy.ndarray"
    )
