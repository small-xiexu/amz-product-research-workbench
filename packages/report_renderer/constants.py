"""Legacy report renderer constants.

这些常量服务旧 `report.md` / `report.html` renderer 链路，不作为 CLI P0
新 Stage 9 HTML 报告契约依据。CLI P0 required operator sections 以
`packages.research_core.pipeline.constants.REQUIRED_SECTION_MARKERS` 为准。
"""

FORMAL_REPORT_SECTION_TITLES = (
    "Executive Summary / 当前结论",
    "数据来源与口径",
    "品类选择推导链路",
    "候选方向与边界",
    "市场结构与数据质量",
    "关键词与需求信号",
    "产品属性分布与交叉分析",
    "竞品池与竞品选择逻辑",
    "评论 VOC 与真实痛点",
    "市场机会评分",
    "风险与待验证项",
    "继续研究优先级",
    "下一步动作与证据附录",
)
