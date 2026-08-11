"""
plant_ai

使用延迟导入，避免执行：

    import plant_ai

时立刻加载 torch / open_clip / BioCLIP 相关模块。

游戏侧接口保持不变：

    from plant_ai import analyze_plant
    plant = analyze_plant("image.png")
"""


def analyze_plant(image_path: str, device=None):
    """
    正式游戏接口。
    返回 shared_game_data.PlantData。
    """
    from .plant_analyzer import analyze_plant as _analyze_plant

    return _analyze_plant(
        image_path,
        device=device,
    )


def classify_plant(image, device=None):
    """
    只进行 grass / shrub / flower 分类。
    """
    from .plant_analyzer import classify_plant as _classify_plant

    return _classify_plant(
        image,
        device=device,
    )


def analyze_health(image, device=None):
    """
    返回 shared_game_data.PlantStatus。
    """
    from .health_analyzer import analyze_health as _analyze_health

    return _analyze_health(
        image,
        device=device,
    )


def analyze_health_debug(image, device=None):
    """
    返回六维原始 BioCLIP 调试结果。
    """
    from .health_analyzer import (
        analyze_health_debug as _analyze_health_debug,
    )

    return _analyze_health_debug(
        image,
        device=device,
    )


def get_health_scores(image, device=None):
    """
    返回六维简单字典。
    """
    from .health_analyzer import get_health_scores as _get_health_scores

    return _get_health_scores(
        image,
        device=device,
    )


__all__ = [
    "analyze_plant",
    "classify_plant",
    "analyze_health",
    "analyze_health_debug",
    "get_health_scores",
]