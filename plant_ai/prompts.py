"""
plant_ai/prompts.py

BioCLIP zero-shot 文本提示词。

这里的 grass / shrub / flower 是“游戏视觉类型”，
不是严格的植物学分类层级。

每类使用多个 prompt，再对文本 embedding 求平均，
通常比只使用单个单词更稳定。
"""

CLASS_PROMPTS = {
    "grass": [
        "a photo of a grass-like plant with narrow blade-shaped green leaves",
        "a photo of a tufted grassy plant with many thin linear leaves",
        "a low herbaceous plant that visually resembles grass",
        "a plant dominated by long narrow green leaves and no prominent blossom",
        "a grass-like plant growing as a clump close to the ground",
    ],

    "shrub": [
        "a photo of a woody shrub with many branches and dense green foliage",
        "a bushy woody plant with multiple stems",
        "a compact shrub with dense leaves and visible branching structure",
        "a small woody bush growing above the ground",
        "a perennial shrub dominated by branches and foliage rather than flowers",
    ],

    "flower": [
        "a photo of a flowering plant with a large prominent visible blossom",
        "a plant whose dominant visual feature is a colorful flower",
        "a flowering herbaceous plant with clearly visible petals",
        "an ornamental flowering plant with a conspicuous blossom",
        "a blooming plant where the flower is the main subject of the image",
    ],
}
