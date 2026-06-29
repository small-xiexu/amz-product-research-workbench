#!/usr/bin/env python3
"""Operator-facing language helpers.

The pipeline keeps compact internal enums in JSON contracts, but final HTML/XLSX
deliverables should use readable operating language. This module centralizes
that translation so report generation, workbook generation, and QA use one rule
set instead of category-specific replacements.
"""

from __future__ import annotations

import re
from typing import Any


PUBLIC_STATUS_LABELS: dict[str, str] = {
    # Final verdicts / gates
    "go": "建议进入小批量验证",
    "watch": "建议先验证",
    "no_go": "建议暂停推进",
    "blocked": "当前不满足放行条件",
    "continue": "可继续推进",
    "stop": "建议停止推进",
    # Evaluation ratings
    "strong": "正向信号",
    "moderate": "中等信号",
    "weak": "信号偏弱",
    # Confidence
    "high": "判断置信度高",
    "medium": "判断置信度中等",
    "low": "判断置信度偏低",
    # VOC priorities
    "P0": "必须验证",
    "P1": "重点优化",
    "P2": "建议优化",
    # Keyword / category roles
    "main_traffic": "主攻词",
    "conversion_quality": "转化词",
    "precise_long_tail": "长尾词",
    "mixed_or_excluded": "排除词",
    "primary_reference": "核心参考",
    "high_sales": "高销标杆",
    "new_release": "新品样本",
    "premium": "高端锚点",
    "primary": "核心参考",
    "secondary": "辅助参考",
    "mainline": "主推路线",
    "broad_market": "大盘参考",
    "subcategory_market": "细分战场",
    "mixed_pool": "混合流量池",
    "excluded": "不建议使用",
    # Requirement priorities
    "must": "必须做到",
    "should": "建议做到",
    "nice_to_have": "锦上添花",
}

PUBLIC_LABELS_BY_CONTEXT: dict[str, dict[str, str]] = {
    "confidence": {
        "high": "判断置信度高",
        "medium": "判断置信度中等",
        "low": "判断置信度偏低",
    },
    "rating": {
        "strong": "正向信号",
        "watch": "需要关注",
        "weak": "信号偏弱",
        "blocked": "当前不满足放行条件",
    },
    "verdict": {
        "go": "建议进入小批量验证",
        "watch": "建议先验证",
        "no_go": "建议暂停推进",
        "blocked": "当前不满足放行条件",
    },
    "priority": {
        "P0": "必须验证",
        "P1": "重点优化",
        "P2": "建议优化",
    },
}


PUBLIC_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("P0安全风险", "上市前必须验证的安全可靠性问题"),
    ("P0安全项", "上市前必须验证的安全可靠性项目"),
    ("P0安全责任风险", "上市前必须验证的安全可靠性问题"),
    ("P0痛点", "用户高频核心痛点"),
    ("P1痛点", "重要痛点"),
    ("P2痛点", "次级优化点"),
    ("P0/P1/P2", "优先级"),
    ("致命弱点", "主要差评点"),
    ("致命缺陷", "关键缺陷"),
    ("生死考验", "上市前必须验证的关键风险"),
    ("生存威胁", "会显著影响新品早期表现的风险"),
    ("摧毁整个ASIN", "严重影响该商品后续表现"),
    ("摧毁 ASIN", "严重影响该商品后续表现"),
    ("这是可以摧毁整个ASIN的风险", "这是会严重影响该商品后续表现的风险"),
    ("当前状态下做Go/No-Go是赌博", "当前状态不适合直接做最终放行判断"),
    ("当前状态下做 Go/No-Go 是赌博", "当前状态不适合直接做最终放行判断"),
    ("做Go/No-Go就是赌博", "直接做最终放行判断风险较高"),
    ("从老品嘴里抢流量", "从成熟竞品中争取流量"),
    ("watch而非go", "建议先验证后推进"),
    ("Go / No-Go", "放行判断"),
    ("Go/No-Go", "放行判断"),
    ("go/watch/no_go", "建议进入小批量验证/建议先验证/建议暂停推进"),
    ("WATCH", "观察验证"),
    ("No-Go", "暂停推进"),
    ("Stage 10a validation roadmap", "验证路线图"),
    ("Stage 10a", "深度分析阶段"),
    ("validation roadmap", "验证路线图"),
    ("low_review_sample_count", "低评论可验证样本"),
    ("known_monthly_sales_asin_count", "有明确月销证据的样本"),
)


PUBLIC_TEXT_REGEX_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bP0\b"), "必须验证"),
    (re.compile(r"\bP1\b"), "重点优化"),
    (re.compile(r"\bP2\b"), "建议优化"),
    (re.compile(r"\bconfidence\s*=\s*(high|medium|low)\b", re.IGNORECASE), "判断置信度为\\1"),
    (re.compile(r"\bconfidence\s+(high|medium|low)\b", re.IGNORECASE), "判断置信度为\\1"),
    (re.compile(r"置信度\s*(High|Medium|Low|high|medium|low)"), "判断置信度\\1"),
    (re.compile(r"\bfinal_verdict\s*=\s*(go|watch|no_go|blocked)\b"), "最终判断为\\1"),
    (re.compile(r"\brating\s*=\s*(strong|watch|weak|blocked)\b"), "维度评级为\\1"),
    (re.compile(r"\b(\d{1,3})/(strong|watch|weak|blocked)\b"), "\\1（维度评级为\\2）"),
    (re.compile(r"\bdata_quality\s+blocked\b"), "数据质量当前不满足放行条件"),
    (re.compile(r"\bblocked/weak\b"), "阻断或偏弱"),
    (re.compile(r"\bStage\s*\d+[a-z]?\b", re.IGNORECASE), "业务分析阶段"),
)


PUBLIC_FORBIDDEN_TEXT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bP[0-2]\b", "内部优先级标签裸露，应改为必须验证/重点优化/建议优化"),
    (r"P0安全风险|P0安全项|P0痛点|P1痛点|P2痛点", "内部痛点/风险标签裸露，应翻译成运营可读表达"),
    (r"生死考验|生存威胁|摧毁(?:整个)?ASIN|摧毁\s+ASIN", "惊吓式风险表达，应改为证据-影响-动作"),
    (r"致命弱点|致命缺陷", "过度强烈的竞品表达，应改为主要差评点/关键缺陷"),
    (r"当前状态下做\s*Go/No-Go\s*是赌博|赌博", "情绪化判断表达，应改为判断不稳或需补证据"),
    (r"从老品嘴里抢流量", "过度口语化表达，应改为从成熟竞品中争取流量"),
    (r"\bStage\s*10[ab]?\b", "内部深度分析阶段编号裸露，应改为业务阶段名称"),
    (r"\bconfidence\s*(?:=|:)?\s*(?:High|Medium|Low|high|medium|low)\b", "内部置信度枚举裸露，应改为中文置信度说明"),
    (r"置信度\s*(?:High|Medium|Low|high|medium|low)\b", "内部置信度枚举裸露，应改为中文置信度说明"),
    (r"\bfinal_verdict\b|\brating\s*=", "内部判断字段裸露，应改为运营判断语言"),
    (r"\bblocked/weak\b", "内部评级组合裸露，应改为阻断或偏弱维度"),
    (r"\bWATCH\b", "内部 watch 标签裸露，应改为观察验证"),
)


def public_label(value: Any, *, context: str | None = None) -> str:
    """Return the public label for a compact internal value."""
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""
    context_map = PUBLIC_LABELS_BY_CONTEXT.get(context or "")
    if context_map:
        mapped = context_map.get(raw) or context_map.get(raw.lower())
        if mapped:
            return mapped
    return PUBLIC_STATUS_LABELS.get(raw, public_text(raw))


def public_text(value: Any) -> str:
    """Sanitize a string for operator-facing deliverables."""
    if value is None:
        return ""
    text = str(value)
    for raw, replacement in PUBLIC_TEXT_REPLACEMENTS:
        text = text.replace(raw, replacement)
    for pattern, replacement in PUBLIC_TEXT_REGEX_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    # Apply label words after phrase replacements so "watch而非go" is handled first.
    text = text.replace("判断置信度为high", "判断置信度高")
    text = text.replace("判断置信度为medium", "判断置信度中等")
    text = text.replace("判断置信度为low", "判断置信度偏低")
    text = text.replace("判断置信度High", "判断置信度高")
    text = text.replace("判断置信度Medium", "判断置信度中等")
    text = text.replace("判断置信度Low", "判断置信度偏低")
    text = text.replace("判断置信度为High", "判断置信度高")
    text = text.replace("判断置信度为Medium", "判断置信度中等")
    text = text.replace("判断置信度为Low", "判断置信度偏低")
    text = text.replace("最终判断为go", "最终判断为建议进入小批量验证")
    text = text.replace("最终判断为watch", "最终判断为建议先验证")
    text = text.replace("最终判断为no_go", "最终判断为建议暂停推进")
    text = text.replace("最终判断为blocked", "最终判断为当前不满足放行条件")
    text = text.replace("维度评级为strong", "维度评级为正向信号")
    text = text.replace("维度评级为watch", "维度评级为需要关注")
    text = text.replace("维度评级为weak", "维度评级为信号偏弱")
    text = text.replace("维度评级为blocked", "维度评级为当前不满足放行条件")
    return text


def public_value(value: Any) -> Any:
    """Sanitize string values while preserving non-string values."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in PUBLIC_STATUS_LABELS:
            return public_label(stripped)
        return public_text(value)
    return value


def find_public_language_issues(text: str) -> list[str]:
    """Return public-language violations found in text."""
    hits: list[str] = []
    for pattern, description in PUBLIC_FORBIDDEN_TEXT_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            unique = sorted({m if isinstance(m, str) else "".join(m) for m in matches})[:5]
            hits.append(f"{description}（匹配: {', '.join(unique)}）")
    return hits
