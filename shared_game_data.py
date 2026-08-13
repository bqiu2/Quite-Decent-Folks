"""
shared_game_data.py
===================

项目：植物状态驱动的像素游戏
用途：三人小组之间的【统一数据接口文件】

======================================================================
【重要约定】
======================================================================

这个文件只存放：
1. 三个人之间需要传递的数据结构
2. 三个人共同使用的常量
3. 三个人共同使用的计算规则
4. MediaPipe 控制模块向游戏模块输出的统一动作名称

这个文件不要存放：
1. 植物识别模型具体实现
2. 第一关跑酷逻辑
3. 第二关僵尸逻辑
4. Pygame 绘制代码
5. MediaPipe 检测细节
6. 图片、音频等资源加载逻辑

三个人都可以 import 这个文件，但不要各自复制一份修改。
如果需要改字段名、数值范围或计算规则，三个人先统一后再修改。

推荐模块关系：

成员 A：植物识别 / 状态识别
    图片 -> analyze_plant() -> PlantData

成员 B：第一关跑酷
    PlantData -> run_level1() -> Level1Result
    第一关过程中会修改 PlantData.status 和 PlantData.current_power

成员 C：第二关 + 主程序整合
    PlantData + DifficultyConfig -> run_level2() -> Level2Result
    最后使用 calculate_final_score() 生成 FinalResult
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
import json


# ======================================================================
# 1. 基础类型约定
# ======================================================================

# ----------------------------------------------------------------------
# 植物种类
# ----------------------------------------------------------------------
# grass  = 草
# shrub  = 灌木
# flower = 花
#
# 成员 A 的植物分类模型最终只能输出这三个字符串之一。
# 成员 B、C 不需要知道模型是怎么判断的，只读取 plant.plant_type。
PlantType = Literal["grass", "shrub", "flower"]


# ----------------------------------------------------------------------
# 第一关 MediaPipe Pose 输出动作
# ----------------------------------------------------------------------
# pose_control.py 只向第一关输出以下三个动作：
#
# "jump"   -> 跳跃
# "crouch" -> 下蹲
# "none"   -> 当前没有有效动作
#
# 第一关不要直接读取 MediaPipe 关键点来控制角色。
PoseAction = Literal["jump", "crouch", "none"]


# ----------------------------------------------------------------------
# 第二关 MediaPipe Hands 输出动作
# ----------------------------------------------------------------------
# hand_control.py 只向第二关输出以下三个动作：
#
# "up"   -> 植物向上一条轨道移动
# "down" -> 植物向下一条轨道移动
# "none" -> 当前没有有效动作
HandAction = Literal["up", "down", "none"]


# ----------------------------------------------------------------------
# 第一关可收集元素
# ----------------------------------------------------------------------
#
# pesticide 不属于植物五项基础营养状态，
# 它的作用是改善 pest（害虫健康分数）。
ElementType = Literal[
    "water",
    "light",
    "nitrogen",
    "phosphorus",
    "potassium",
    "pesticide",
]


# ----------------------------------------------------------------------
# 第二关难度
# ----------------------------------------------------------------------
DifficultyName = Literal["easy", "normal", "hard"]


# ======================================================================
# 2. 全局数值范围
# ======================================================================

# 植物五项状态以及 pest 状态统一使用 0.0 ~ 1.0。
STATUS_MIN = 0.0
STATUS_MAX = 1.0

# 战力统一使用 0 ~ 100。
POWER_MIN = 0.0
POWER_MAX = 100.0

# 第一关初始生命值。
LEVEL1_MAX_HP = 3

# 第一关默认时间限制，单位：秒。
LEVEL1_TIME_LIMIT = 40.0

# 第二关轨道数量。
LEVEL2_LANE_COUNT = 5

# 第二关固定两大波僵尸。
LEVEL2_WAVE_COUNT = 2


# ======================================================================
# 3. 植物状态数据
# ======================================================================

@dataclass
class PlantStatus:
    """
    植物六维状态。

    【统一规定】
    所有值范围都必须是 0.0 ~ 1.0。
    所有维度都是“数值越高，植物状态越好”。

    这样可以避免 pest 和其他维度方向相反导致程序写错。

    字段说明
    ------------------------------------------------------------------
    water:
        水分状态。
        0.0 = 严重缺水
        1.0 = 水分状态最佳

    light:
        光照状态。
        0.0 = 严重缺光
        1.0 = 光照状态最佳

    nitrogen:
        氮元素状态。
        0.0 = 严重缺氮
        1.0 = 氮状态最佳

    phosphorus:
        磷元素状态。
        0.0 = 严重缺磷
        1.0 = 磷状态最佳

    potassium:
        钾元素状态。
        0.0 = 严重缺钾
        1.0 = 钾状态最佳

    pest:
        害虫健康系数。
        注意：这里不是“害虫数量”。

        1.0 = 没有害虫 / 害虫影响极低
        0.0 = 害虫影响极严重

        因此所有属性都满足：
        分数越高 -> 越健康。
    """

    water: float = 0.5
    light: float = 0.5
    nitrogen: float = 0.5
    phosphorus: float = 0.5
    potassium: float = 0.5
    pest: float = 1.0


# ======================================================================
# 4. 植物主数据 PlantData
# ======================================================================

@dataclass
class PlantData:
    """
    玩家植物在整个游戏中的核心数据。

    这是成员 A -> 成员 B -> 成员 C 之间最重要的数据对象。

    字段说明
    ------------------------------------------------------------------
    plant_id:
        本次植物的唯一 ID。
        建议格式：
            PLANT_0001
            PLANT_0002

        成员 A / 主程序负责生成。

    plant_type:
        植物类型，只允许：
            "grass"
            "shrub"
            "flower"

    image_path:
        玩家上传的原始植物图片路径。
        例如：
            "uploads/PLANT_0001.jpg"

        游戏显示原图或重新分析时可以使用。

    status:
        PlantStatus 对象，保存水、光、N、P、K、害虫六维状态。

    initial_power:
        玩家上传植物并完成第一次识别后得到的初始战力。
        范围：0 ~ 100。

        【重要】
        第一关收集元素后不要修改这个值。
        它用于最终评分时记录“最开始植物有多强”。

    current_power:
        当前实时战力。
        范围：0 ~ 100。

        第一关拾取资源后要重新计算并更新该值。
        第二关使用 current_power 决定植物攻击能力。
    """

    plant_id: str
    plant_type: PlantType
    image_path: str
    status: PlantStatus
    initial_power: float
    current_power: float


# ======================================================================
# 5. 植物状态 / 战力共同规则
# ======================================================================

# 第一关每收集 1 个对应元素，对状态增加多少。
#
# 后续如果觉得游戏升级太快/太慢，只统一改这里，
# 不要在 level1.py 的不同位置到处写 0.08。
ELEMENT_GAIN = {
    "water": 0.08,
    "light": 0.08,
    "nitrogen": 0.08,
    "phosphorus": 0.08,
    "potassium": 0.08,
}

# 每获得一个杀虫剂，对 pest 健康系数增加多少。
PESTICIDE_GAIN = 0.15


def clamp(value: float, minimum: float, maximum: float) -> float:
    """
    把 value 限制在 [minimum, maximum] 范围内。

    例如：
        clamp(1.2, 0.0, 1.0) -> 1.0
        clamp(-0.1, 0.0, 1.0) -> 0.0
    """
    return max(minimum, min(maximum, value))


def normalize_plant_status(status: PlantStatus) -> PlantStatus:
    """
    将植物六维状态全部限制在 0.0 ~ 1.0。

    建议：
    - 成员 A 模型输出 PlantStatus 后调用一次。
    - 第一关每次修改属性后调用一次。
    """
    status.water = clamp(status.water, STATUS_MIN, STATUS_MAX)
    status.light = clamp(status.light, STATUS_MIN, STATUS_MAX)
    status.nitrogen = clamp(status.nitrogen, STATUS_MIN, STATUS_MAX)
    status.phosphorus = clamp(status.phosphorus, STATUS_MIN, STATUS_MAX)
    status.potassium = clamp(status.potassium, STATUS_MIN, STATUS_MAX)
    status.pest = clamp(status.pest, STATUS_MIN, STATUS_MAX)
    return status


def calculate_power(status: PlantStatus) -> float:
    """
    根据植物状态统一计算战力。

    五项基础状态：
        water
        light
        nitrogen
        phosphorus
        potassium

    使用“弱化木桶效应”：

        基础状态 =
            0.7 × 五项最小值
            + 0.3 × 五项平均值

        最终战力 =
            100 × 基础状态 × pest

    为什么这样设计：
    1. 最弱的一项仍然占主要作用，体现木桶效应。
    2. 其他四项也会影响战力，不会完全失去意义。
    3. pest 作为负面影响最后相乘。

    返回值范围：
        0 ~ 100

    示例：
        water      = 0.8
        light      = 0.9
        nitrogen   = 0.5
        phosphorus = 0.7
        potassium  = 0.8
        pest       = 0.9

        战力会由该函数统一计算。

    【重要】
    三个人不要自己再写另一套战力公式。
    """
    status = normalize_plant_status(status)

    basic_values = [
        status.water,
        status.light,
        status.nitrogen,
        status.phosphorus,
        status.potassium,
    ]

    weakest = min(basic_values)
    average = sum(basic_values) / len(basic_values)

    base_score = 0.7 * weakest + 0.3 * average
    power = 100.0 * base_score * status.pest

    power = clamp(power, POWER_MIN, POWER_MAX)
    return round(power, 2)


def refresh_power(plant: PlantData) -> float:
    """
    根据 plant.status 重新计算 current_power。

    第一关改变植物状态后直接调用：

        refresh_power(plant)

    返回新的 current_power。
    """
    plant.current_power = calculate_power(plant.status)
    return plant.current_power


def apply_element(plant: PlantData, element: ElementType) -> None:
    """
    第一关拾取资源后，统一通过这个函数修改植物状态。

    参数：
        plant:
            当前玩家植物。

        element:
            "water"
            "light"
            "nitrogen"
            "phosphorus"
            "potassium"
            "pesticide"

    执行效果：
    1. 修改对应状态。
    2. 自动限制到 0~1。
    3. 自动刷新 current_power。

    第一关成员建议直接调用：

        apply_element(plant, "water")
        apply_element(plant, "nitrogen")
        apply_element(plant, "pesticide")
    """

    if element in ELEMENT_GAIN:
        old_value = getattr(plant.status, element)
        new_value = old_value + ELEMENT_GAIN[element]
        setattr(
            plant.status,
            element,
            clamp(new_value, STATUS_MIN, STATUS_MAX),
        )

    elif element == "pesticide":
        plant.status.pest = clamp(
            plant.status.pest + PESTICIDE_GAIN,
            STATUS_MIN,
            STATUS_MAX,
        )

    refresh_power(plant)


# ======================================================================
# 6. 第一关结果数据
# ======================================================================

@dataclass
class Level1Result:
    """
    第一关结束后传给主程序 / 第二关 / 结算页面的数据。

    成员 B 负责生成。

    字段说明
    ------------------------------------------------------------------
    completed:
        第一关是否正常结束。
        当前设计中：
        - 倒计时结束
        - 或 HP 变为 0
        都可以进入第二关。

        因此通常可以设为 True。
        如果程序异常退出等情况，可以设为 False。

    remaining_hp:
        第一关结束剩余生命值。
        范围：0 ~ LEVEL1_MAX_HP（默认 3）。

    time_survived:
        第一关实际坚持时间，单位：秒。
        范围：0 ~ 60。

    collected_xxx:
        每种资源实际收集数量。
        用于结果页面和第一关评分。

    pest_hits:
        玩家碰到害虫的次数。

    power_before:
        进入第一关时的战力。

    power_after:
        第一关结束时的战力。

    score:
        第一关单独得分。
        建议范围：0 ~ 100。
    """

    completed: bool

    remaining_hp: int
    time_survived: float

    collected_water: int = 0
    collected_light: int = 0
    collected_nitrogen: int = 0
    collected_phosphorus: int = 0
    collected_potassium: int = 0
    collected_pesticide: int = 0

    pest_hits: int = 0

    power_before: float = 0.0
    power_after: float = 0.0

    score: float = 0.0


# ======================================================================
# 7. 第二关难度配置
# ======================================================================

@dataclass(frozen=True)
class DifficultyConfig:
    """
    第二关难度参数。

    frozen=True：
        创建后不应该在游戏过程中随意修改。

    字段说明
    ------------------------------------------------------------------
    name:
        "easy" / "normal" / "hard"

    zombie_hp_multiplier:
        僵尸基础血量倍率。

    zombie_speed_multiplier:
        僵尸基础移动速度倍率。

    zombie_count_multiplier:
        僵尸基础数量倍率。

    score_multiplier:
        最终结算时的难度奖励倍率。
    """

    name: DifficultyName
    zombie_hp_multiplier: float
    zombie_speed_multiplier: float
    zombie_count_multiplier: float
    score_multiplier: float


DIFFICULTIES: dict[DifficultyName, DifficultyConfig] = {
    "easy": DifficultyConfig(
        name="easy",
        zombie_hp_multiplier=0.8,
        zombie_speed_multiplier=0.8,
        zombie_count_multiplier=0.8,
        score_multiplier=1.0,
    ),

    "normal": DifficultyConfig(
        name="normal",
        zombie_hp_multiplier=1.0,
        zombie_speed_multiplier=1.0,
        zombie_count_multiplier=1.0,
        score_multiplier=1.2,
    ),

    "hard": DifficultyConfig(
        name="hard",
        zombie_hp_multiplier=1.3,
        zombie_speed_multiplier=1.2,
        zombie_count_multiplier=1.25,
        score_multiplier=1.5,
    ),
}


# ======================================================================
# 8. 三种植物的第二关攻击配置
# ======================================================================

# 这里保存三种植物在第二关中共同需要的基础攻击参数。
#
# 成员 C 根据 plant.plant_type 读取配置。
#
# 注意：
# base_damage 是基础伤害，真正伤害还会根据 current_power 进行计算。
#
# grass：
#   剑气，速度快，偏单体。
#
# shrub：
#   地震波，速度较慢，可穿透多个敌人。
#
# flower：
#   花瓣攻击，可一次发射多个花瓣。
ATTACK_CONFIG = {
    "grass": {
        "attack_name": "sword_wave",
        "base_damage": 20.0,
        "projectile_speed": 14.0,
        "penetration": 1,
        "projectile_count": 1,
        "cooldown": 0.45,
    },

    "shrub": {
        "attack_name": "earthquake",
        "base_damage": 16.0,
        "projectile_speed": 7.0,
        "penetration": 5,
        "projectile_count": 1,
        "cooldown": 0.80,
    },

    "flower": {
        "attack_name": "petal_shot",
        "base_damage": 10.0,
        "projectile_speed": 11.0,
        "penetration": 1,
        "projectile_count": 3,
        "cooldown": 0.60,
    },
}


def calculate_attack_damage(
    plant: PlantData,
    base_damage: float,
) -> float:
    """
    第二关统一攻击力计算。

    current_power 范围为 0~100。

    伤害倍率：
        0.5 + current_power / 100

    因此：
        战力 0   -> 0.5 倍基础伤害
        战力 50  -> 1.0 倍基础伤害
        战力 100 -> 1.5 倍基础伤害

    这样可以保证：
    - 植物状态很差时仍然能攻击，不至于完全无法游戏。
    - 第一关提升植物状态后，会明显提高第二关伤害。
    """
    multiplier = 0.5 + plant.current_power / 100.0
    return round(base_damage * multiplier, 2)


# ======================================================================
# 9. 第二关结果数据
# ======================================================================

@dataclass
class Level2Result:
    """
    第二关结束后输出的数据。

    成员 C 负责生成。

    字段说明
    ------------------------------------------------------------------
    victory:
        True  = 两波僵尸全部消灭，玩家胜利。
        False = 至少有僵尸突破防线到达房子，玩家失败。

    difficulty:
        本次选择的难度。

    zombies_total:
        本局生成的僵尸总数。

    zombies_killed:
        玩家消灭的僵尸数量。

    zombies_escaped:
        突破防线的僵尸数量。

    wave_reached:
        玩家到达第几波。
        当前范围：1 ~ LEVEL2_WAVE_COUNT（默认 2）。

    battle_time:
        第二关持续时间，单位：秒。

    score:
        第二关单独表现分。
        建议范围：0 ~ 100。
        难度倍率不要重复计算到这里；
        最终评分时统一使用 DifficultyConfig.score_multiplier。
    """

    victory: bool
    difficulty: DifficultyName

    zombies_total: int
    zombies_killed: int
    zombies_escaped: int

    wave_reached: int
    battle_time: float

    score: float


# ======================================================================
# 10. 最终结算数据
# ======================================================================

@dataclass
class FinalResult:
    """
    整局游戏最终结算数据。

    主要用于：
    - 最终结算界面
    - 排行榜
    - 保存本次游戏记录

    字段说明
    ------------------------------------------------------------------
    plant_id:
        本局植物 ID。

    plant_type:
        草 / 灌木 / 花。

    initial_power:
        玩家刚上传植物时的初始战力。

    final_power:
        第一关结束后的最终植物战力，
        也是第二关主要使用的植物战力。

    level1_score:
        第一关得分，建议 0~100。

    level2_score:
        第二关得分，建议 0~100。

    difficulty:
        第二关难度。

    difficulty_multiplier:
        对应难度的最终得分倍率。

    final_score:
        游戏最终得分。

    victory:
        第二关是否最终获胜。
    """

    plant_id: str
    plant_type: PlantType

    initial_power: float
    final_power: float

    level1_score: float
    level2_score: float

    difficulty: DifficultyName
    difficulty_multiplier: float

    final_score: float
    victory: bool


# ======================================================================
# 11. 最终评分规则
# ======================================================================

# 三部分基础权重。
#
# 当前设计：
# 初始植物战力 40%
# 第一关表现     30%
# 第二关表现     30%
#
# 三个权重之和必须为 1.0。
FINAL_WEIGHT_INITIAL_POWER = 0.40
FINAL_WEIGHT_LEVEL1 = 0.30
FINAL_WEIGHT_LEVEL2 = 0.30


def calculate_final_score(
    plant: PlantData,
    level1: Level1Result,
    level2: Level2Result,
    difficulty: DifficultyConfig,
) -> FinalResult:
    """
    统一计算最终得分并返回 FinalResult。

    基础分：
        0.4 × 初始植物战力
        + 0.3 × 第一关得分
        + 0.3 × 第二关得分

    最终分：
        基础分 × 难度倍率

    【重要】
    最终评分只在这里计算。
    不要让 main.py、level1.py、level2.py 分别出现不同版本的公式。
    """

    base_score = (
        FINAL_WEIGHT_INITIAL_POWER * plant.initial_power
        + FINAL_WEIGHT_LEVEL1 * level1.score
        + FINAL_WEIGHT_LEVEL2 * level2.score
    )

    final_score = base_score * difficulty.score_multiplier
    final_score = round(final_score, 2)

    return FinalResult(
        plant_id=plant.plant_id,
        plant_type=plant.plant_type,
        initial_power=plant.initial_power,
        final_power=plant.current_power,
        level1_score=level1.score,
        level2_score=level2.score,
        difficulty=difficulty.name,
        difficulty_multiplier=difficulty.score_multiplier,
        final_score=final_score,
        victory=level2.victory,
    )


# ======================================================================
# 12. JSON 保存 / 读取辅助函数
# ======================================================================

def save_game_result(result: FinalResult, file_path: str) -> None:
    """
    将最终游戏结果保存为 JSON 文件。

    示例：
        save_game_result(
            final_result,
            "data/result_PLANT_0001.json"
        )

    ensure_ascii=False：
        后续即使 JSON 中加入中文，也不会变成 Unicode 转义。
    """
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            asdict(result),
            f,
            ensure_ascii=False,
            indent=4,
        )


def plant_to_dict(plant: PlantData) -> dict:
    """
    将 PlantData 转换成普通字典。

    适合：
    - 调试打印
    - JSON 保存
    - 网络接口
    """
    return asdict(plant)


# ======================================================================
# 13. 三个成员必须实现的统一函数签名（接口说明）
# ======================================================================

"""
下面只是接口说明，不在这个共享文件中真正实现。

======================================================================
成员 A：植物识别
======================================================================

文件建议：
    plant_ai/plant_analyzer.py

必须提供：

    def analyze_plant(image_path: str) -> PlantData:
        ...

作用：
    输入玩家上传图片路径。
    输出完整 PlantData。

成员 A 至少需要填写：
    plant_id
    plant_type
    image_path
    status.water
    status.light
    status.nitrogen
    status.phosphorus
    status.potassium
    status.pest
    initial_power
    current_power

其中：
    initial_power == current_power
    应该在第一次分析结束时成立。


======================================================================
成员 B：第一关
======================================================================

文件建议：
    level1/level1.py

必须提供：

    def run_level1(plant: PlantData) -> Level1Result:
        ...

作用：
    输入 PlantData。
    运行第一关。
    第一关期间可调用 apply_element() 修改 plant。
    最终返回 Level1Result。

【注意】
plant 是同一个对象。
第一关结束后：
    plant.current_power
    plant.status
已经是更新后的值。


======================================================================
成员 C：第二关
======================================================================

文件建议：
    level2/level2.py

必须提供：

    def run_level2(
        plant: PlantData,
        difficulty: DifficultyConfig,
    ) -> Level2Result:
        ...

作用：
    输入第一关更新后的 PlantData 和难度配置。
    运行第二关。
    返回 Level2Result。


======================================================================
成员 B：Pose 控制
======================================================================

文件建议：
    vision/pose_control.py

必须提供：

    def get_pose_action(frame) -> PoseAction:
        ...

只能返回：
    "jump"
    "crouch"
    "none"


======================================================================
成员 C：Hand 控制
======================================================================

文件建议：
    vision/hand_control.py

必须提供：

    def get_hand_action(frame) -> HandAction:
        ...

只能返回：
    "up"
    "down"
    "none"


======================================================================
主程序调用流程
======================================================================

    from shared_game_data import DIFFICULTIES, calculate_final_score

    # 1. 上传并分析植物
    plant = analyze_plant(image_path)

    # 2. 第一关
    level1_result = run_level1(plant)

    # 3. 玩家选择难度
    difficulty = DIFFICULTIES["normal"]

    # 4. 第二关
    level2_result = run_level2(
        plant,
        difficulty,
    )

    # 5. 最终结算
    final_result = calculate_final_score(
        plant,
        level1_result,
        level2_result,
        difficulty,
    )

整个项目最重要的数据流：

    图片
      ↓
    PlantData
      ↓
    第一关
      ↓
    PlantData（状态被更新） + Level1Result
      ↓
    第二关
      ↓
    Level2Result
      ↓
    FinalResult
"""
