"""
plant_ai/config.py

BioCLIP 植物游戏类型分类配置。
"""

import torch

# BioCLIP 官方 Hugging Face / OpenCLIP 模型名
MODEL_NAME = "hf-hub:imageomics/bioclip"

# 游戏中只保留三种植物视觉类型
PLANT_TYPES = ("grass", "shrub", "flower")

# 与游戏侧约定的 ID
PLANT_TYPE_TO_ID = {
    "grass": 0,
    "shrub": 1,
    "flower": 2,
}

# 自动选择运行设备
DEFAULT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 是否在首次加载时打印模型信息
VERBOSE = True
