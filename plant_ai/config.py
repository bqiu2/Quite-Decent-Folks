from __future__ import annotations

from pathlib import Path

MODEL_NAME = "google/siglip2-base-patch16-224"

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
REFERENCE_DIR = PACKAGE_DIR / "reference_images"
CACHE_DIR = PACKAGE_DIR / ".cache"
PROTOTYPE_CACHE = CACHE_DIR / "type_prototypes.npz"
DATA_DIR = PROJECT_DIR / "data"
PLANT_ID_COUNTER = DATA_DIR / "plant_id_counter.txt"

PLANT_TYPES = ("grass", "shrub", "flower")
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# 至少建议每类 15~30 张。代码允许 5 张起步，但太少时稳定性会明显下降。
MIN_REFERENCE_IMAGES_PER_CLASS = 5
RECOMMENDED_REFERENCE_IMAGES_PER_CLASS = 20
REFERENCE_BATCH_SIZE = 8

# 图像原型相似度经过 softmax 时的温度。越小，分类越“果断”。
TYPE_SOFTMAX_TEMPERATURE = 0.06

# flower 不再等价于“被子植物/会开花的植物”。
# 游戏中 flower 定义为：照片中能明显看到花、花瓣或花序。
FLOWER_PRESENCE_THRESHOLD = 0.58
FLOWER_STRONG_THRESHOLD = 0.72
FLOWER_PROTOTYPE_MARGIN = 0.012

# 六维健康分析采用可见表型估计。N/P/K/light 可靠性低于 water/pest，
# 因此会自动向中性健康值收缩，避免输出虚假的极端精确分数。
HEALTH_NEUTRAL_SCORE = 0.65
HEALTH_LEVEL_VALUES = (0.0, 0.25, 0.50, 0.75, 1.0)
HEALTH_LEVEL_TEMPERATURE = 1.0
HEALTH_VISUAL_RELIABILITY = {
    "water": 0.82,
    "light": 0.48,
    "nitrogen": 0.52,
    "phosphorus": 0.35,
    "potassium": 0.50,
    "pest": 0.82,
}

# 植物主体自动裁剪参数。
AUTO_CROP_ENABLED = True
CROP_PADDING_RATIO = 0.12
MIN_VEGETATION_COVERAGE = 0.015
MIN_CROP_AREA_RATIO = 0.18
