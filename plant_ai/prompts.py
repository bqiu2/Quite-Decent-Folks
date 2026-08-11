from __future__ import annotations

# ------------------------------
# 类型后备 Prompt
# ------------------------------
# flower 特意写成“照片中明显能看到花”，避免把所有被子植物都判为 flower。
TYPE_FALLBACK_PROMPTS = {
    "grass": [
        "a grass-like plant dominated by long narrow blade-shaped leaves",
        "a tufted herbaceous grass with thin linear leaves and no woody branching",
        "a lawn-like or ornamental grass plant with narrow strap-shaped foliage",
    ],
    "shrub": [
        "a leafy shrub or bush with branching stems and mostly broad leaves",
        "a compact bushy plant with multiple branches and broad foliage",
        "a woody or semi-woody shrub-like plant without clearly visible blossoms",
    ],
}

FLOWER_POSITIVE_PROMPTS = [
    "a plant with clearly visible flowers, blossoms, petals, or flower heads",
    "a plant where one or more obvious flower blooms are visible",
    "visible petals and blossoms are clearly present on the plant",
]

FLOWER_NEGATIVE_PROMPTS = [
    "a leafy plant with no visible flowers or blossoms",
    "a plant showing foliage only, with no obvious petals or flower blooms",
    "no visible flower bloom is present; the image mainly shows leaves and stems",
]


# ------------------------------
# 六维状态 Prompt
# ------------------------------
# 所有维度保持：0 = 状态很差，1 = 状态很好。
# N/P/K 仅描述“可见缺素表型”，不是测量真实组织元素含量。
HEALTH_PROMPTS: dict[str, list[list[str]]] = {
    "water": [
        [
            "a severely water-stressed plant with strong wilting, drooping, curling and dry tissue",
            "a badly dehydrated plant with limp leaves and extensive dry or crispy damage",
        ],
        [
            "a plant with clear water deficiency, visible wilting and dry leaf areas",
            "a noticeably dehydrated plant with drooping leaves and water-stress symptoms",
        ],
        [
            "a plant with mild or ambiguous water stress and some loss of leaf firmness",
            "a plant showing moderate water status, neither severely wilted nor fully turgid",
        ],
        [
            "a mostly well-hydrated plant with firm leaves and only slight water-stress signs",
            "a generally turgid plant with adequate water and little visible wilting",
        ],
        [
            "a healthy well-hydrated plant with firm turgid leaves and no visible wilting",
            "a fully hydrated plant with fresh firm foliage and no dry water-stress symptoms",
        ],
    ],
    "light": [
        [
            "a severely light-starved plant with strong etiolation, weak elongated growth and pale foliage",
            "a plant showing severe insufficient-light symptoms with very stretched weak pale growth",
        ],
        [
            "a plant with clear low-light stress, elongated growth and noticeably pale or weak foliage",
            "a plant showing obvious insufficient-light symptoms and stretched stems",
        ],
        [
            "a plant with mild or ambiguous signs of insufficient light",
            "a plant with average light-related appearance and some possible stretching or paleness",
        ],
        [
            "a plant with generally adequate light, compact growth and mostly normal foliage",
            "a mostly healthy plant with little visible evidence of insufficient light",
        ],
        [
            "a plant with healthy compact growth and normal foliage showing no visible low-light stress",
            "a well-lit healthy plant with sturdy growth and no etiolation",
        ],
    ],
    "nitrogen": [
        [
            "a plant with severe visible nitrogen-deficiency symptoms, extensive pale yellow chlorosis especially on older leaves",
            "a strongly nitrogen-deficient-looking plant with widespread yellowing of older foliage and weak growth",
        ],
        [
            "a plant with clear visible nitrogen-deficiency-like symptoms and yellow older leaves",
            "a plant with obvious generalized chlorosis consistent with nitrogen deficiency",
        ],
        [
            "a plant with mild or ambiguous nitrogen-deficiency-like yellowing",
            "a plant with moderate leaf greenness and some possible nitrogen-related chlorosis",
        ],
        [
            "a mostly green healthy-looking plant with little visible nitrogen-deficiency-like chlorosis",
            "a plant with generally adequate-looking nitrogen status and mostly green leaves",
        ],
        [
            "a vigorous green plant with no visible nitrogen-deficiency-like yellowing",
            "a healthy plant with consistently green foliage and no generalized chlorosis",
        ],
    ],
    "phosphorus": [
        [
            "a plant with severe visible phosphorus-deficiency-like symptoms, strong stunting and abnormal dark purple or reddish older foliage",
            "a severely phosphorus-stressed-looking plant with pronounced purple red discoloration and poor growth",
        ],
        [
            "a plant with clear phosphorus-deficiency-like dark green purple or reddish discoloration and stunting",
            "a plant showing obvious visible symptoms consistent with phosphorus deficiency",
        ],
        [
            "a plant with mild or ambiguous phosphorus-deficiency-like discoloration",
            "a plant with moderate appearance and some possible dark or purplish stress symptoms",
        ],
        [
            "a mostly healthy-looking plant with little visible phosphorus-deficiency-like discoloration",
            "a plant with generally normal foliage and only slight possible phosphorus stress",
        ],
        [
            "a healthy plant with normal foliage and no visible phosphorus-deficiency-like purple or red stress symptoms",
            "a normally growing plant showing no obvious visible phosphorus-deficiency-like signs",
        ],
    ],
    "potassium": [
        [
            "a plant with severe visible potassium-deficiency-like symptoms, extensive yellow brown scorched leaf margins and necrosis",
            "a severely potassium-stressed-looking plant with widespread marginal burn and dead leaf edges",
        ],
        [
            "a plant with clear potassium-deficiency-like yellowing and browning along leaf margins",
            "a plant showing obvious marginal scorch and edge necrosis consistent with potassium deficiency",
        ],
        [
            "a plant with mild or ambiguous potassium-deficiency-like leaf-edge yellowing or browning",
            "a plant with moderate foliage and some possible marginal potassium stress",
        ],
        [
            "a mostly healthy-looking plant with little marginal scorch or potassium-deficiency-like damage",
            "a plant with generally intact leaf margins and only slight possible potassium stress",
        ],
        [
            "a healthy plant with intact green leaf margins and no visible potassium-deficiency-like scorch",
            "a plant with normal leaf edges and no obvious marginal necrosis",
        ],
    ],
    "pest": [
        [
            "a plant severely damaged by pests with many holes, chewed edges, feeding damage, webbing or visible insects",
            "a heavily pest-damaged plant with extensive insect feeding injury and badly damaged leaves",
        ],
        [
            "a plant with clear pest damage such as multiple holes, chewed leaf edges or visible insects",
            "a noticeably insect-damaged plant with obvious feeding injury",
        ],
        [
            "a plant with mild or ambiguous pest damage and a few possible feeding marks",
            "a plant with moderate leaf damage that may include some pest injury",
        ],
        [
            "a mostly intact plant with very little visible pest damage",
            "a generally healthy plant with only isolated minor holes or feeding marks",
        ],
        [
            "a healthy plant with intact leaves and no visible pest damage, holes, chewing, webbing or insects",
            "a pest-free-looking plant with clean intact foliage and no visible feeding injury",
        ],
    ],
}
