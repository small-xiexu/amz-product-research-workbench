#!/usr/bin/env python3
"""Pipeline constants — QA version, report sections, HTML forbidden patterns."""

from __future__ import annotations

QA_RULE_VERSION = "2026-06-23-v2"
REPORT_VERDICT_LABELS = {
    "继续看": "建议进入小批量验证",
    "谨慎继续": "建议补齐数据后再评估",
    "暂缓": "建议暂停推进",
}
ALLOWED_VERDICTS = set(REPORT_VERDICT_LABELS.values())
FORBIDDEN_HTML_PATTERNS = [
    # 抽象路线标签：运营看不懂"路线A/B"是什么意思
    (r"路线[A-Z0-9]", "抽象路线标签（如路线A/路线B/路线1），必须用业务描述词（如吊扇除尘/纯钢丝刷）"),
    # 内部执行术语：不能暴露给运营
    (r"\bAgent\b", "内部术语 Agent，HTML 中不得出现"),
    (r"\bMCP\b", "内部术语 MCP，HTML 中不得出现（数据来源写 Sorftime 即可）"),
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
]
REQUIRED_SECTION_MARKERS = (
    "类目全景",
    "数据来源与口径",
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

