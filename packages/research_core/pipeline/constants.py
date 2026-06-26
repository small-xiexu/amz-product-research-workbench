#!/usr/bin/env python3
"""Pipeline constants — QA version, report sections, HTML forbidden patterns."""

from __future__ import annotations

QA_RULE_VERSION = "2026-06-25-p8-v2"
VOC_MIN_REVIEW_THRESHOLD = 30  # stage_7_voc_gate 最低评论数
REPORT_VERDICT_LABELS = {
    "继续看": "建议进入小批量验证",
    "谨慎继续": "建议补齐数据后再评估",
    "暂缓": "建议暂停推进",
}
ALLOWED_VERDICTS = set(REPORT_VERDICT_LABELS.values())
FORBIDDEN_HTML_PATTERNS = [
    # 抽象路线标签：运营看不懂"路线A/B"是什么意思
    (r"路线[A-Z0-9](?![A-Z0-9])", "抽象路线标签（如路线A/路线B/路线1），必须用业务描述词（如吊扇除尘/纯钢丝刷）"),
    # 内部执行术语：不能暴露给运营
    (r"\bAgent\b", "内部术语 Agent，HTML 中不得出现"),
    (r"\bMCP\b", "内部术语 MCP，HTML 中不得出现"),
    (r"\btool\b", "内部术语 tool，HTML 中不得出现"),
    (r"\bpacket\b", "内部术语 packet，HTML 中不得出现"),
    (r"\bpipeline\b", "内部术语 pipeline，HTML 中不得出现"),
    (r"\bspawn\b", "内部术语 spawn，HTML 中不得出现"),
    (r"\bevidence_packet\b", "内部术语 evidence_packet，HTML 中不得出现"),
    (r"\bsource_path\b", "内部术语 source_path，HTML 中不得出现"),
    # 虚假宣传常用措辞
    (r"保证.*月销[0-9万kK]+", "虚假承诺类措辞，不得出现'保证月销X万'"),
    (r"绝对.*爆款", "虚假宣传措辞，不得出现'绝对爆款'"),
    (r"100%.*成功", "虚假宣传措辞，不得出现'100%成功'"),
    (r"零风险", "虚假宣传措辞，不得出现'零风险'"),
    (r"稳赚", "虚假宣传措辞，不得出现'稳赚'"),
    (r"包赚", "虚假宣传措辞，不得出现'包赚'"),
    # 数据源品牌名泄漏：报告不应暴露使用了哪个数据工具
    (r"卖家精灵", "数据源品牌名泄漏，不得出现'卖家精灵'"),
    (r"Sorftime", "数据源品牌名泄漏，不得出现'Sorftime'"),
    # 冲突过程泄漏：报告不应暴露数据融合中的不一致
    (r"数据源冲突", "冲突过程泄漏，不得出现'数据源冲突'"),
    (r"数据不一致", "冲突过程泄漏，不得出现'数据不一致'"),
    (r"两个数据源", "数据源对比泄漏，不得出现'两个数据源'"),
    (r"卖家精灵显示", "数据源对比泄漏，不得出现'卖家精灵显示'"),
    (r"Sorftime显示", "数据源对比泄漏，不得出现'Sorftime显示'"),
    # 内部产物概念：报告不应暴露后台技术产物
    (r"\bsnapshot\b", "内部产物概念泄漏，不得出现'snapshot'"),
    (r"\bschema_version\b", "内部产物概念泄漏，不得出现'schema_version'"),
    (r"\bexecution_provenance\b", "内部产物概念泄漏，不得出现'execution_provenance'"),
    # 冲突复核过程泄漏
    (r"conflict_review", "冲突复核过程泄漏，不得出现'conflict_review'"),
    (r"冲突复核", "冲突复核过程泄漏，不得出现'冲突复核'"),
    (r"融合策略", "冲突复核过程泄漏，不得出现'融合策略'"),
]
REQUIRED_SECTION_MARKERS = (
    "类目全景",
    "核心竞品",
    "用户痛点",
    "价格带分布",
    "关键词与流量策略",
    "风险与下一步",
)
VOC_REQUIRED_EVIDENCE_FIELDS = ("review_id", "quote", "rating", "asin")
REQUIRED_REPORT_DATA_SECTIONS = (
    "hero",
    "category_panorama",
    "data_sources",
    "competitors",
    "pain_points",
    "price_bands",
    "keywords",
    "risks",
    "advantages",
    "gonogo_conditions",
    "next_steps",
)

REQUIRED_REPORT_DATA_DECLARATIONS = (
    "run_id",
    "evidence_sources",
)
