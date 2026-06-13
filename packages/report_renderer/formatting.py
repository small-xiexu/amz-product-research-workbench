"""无状态格式化/工具函数（从 render_report.py R2 抽离，纯移动不改逻辑）。"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime


def _format_number(value: object) -> str:
    if isinstance(value, (int, float)):
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"
    return str(value)


def _format_count_items(items: object, limit: int = 5) -> str:
    if not isinstance(items, list):
        return ""
    parts = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        count = item.get("count")
        if name:
            parts.append(f"{name} {count}" if count not in (None, "") else name)
    return "；".join(parts)


def _site_currency_code(site: object) -> str:
    text = str(site or "").strip().upper()
    mapping = {
        "US": "USD",
        "CA": "CAD",
        "UK": "GBP",
        "EU": "EUR",
        "DE": "EUR",
        "FR": "EUR",
        "IT": "EUR",
        "ES": "EUR",
        "JP": "JPY",
        "AU": "AUD",
        "MX": "MXN",
        "USD": "USD",
        "CAD": "CAD",
        "GBP": "GBP",
        "EUR": "EUR",
        "JPY": "JPY",
        "AUD": "AUD",
        "MXN": "MXN",
        "CNY": "CNY",
        "RMB": "RMB",
    }
    return mapping.get(text, text or "USD")


def _format_money(value: object, currency_code: str) -> str:
    if value in (None, "", "待填", "待补"):
        return "待补"
    if isinstance(value, (int, float)):
        formatted = f"{abs(value):,.2f}" if abs(value) >= 1000 else f"{abs(value):.2f}"
        sign = "-" if value < 0 else ""
        return f"{sign}{formatted}"
    return str(value)


def _normalize_money_text(value: object, currency_code: str) -> str:
    text = str(value or "")
    if not text:
        return text
    text = text.replace("美元", "")
    text = text.replace("美金", "")
    text = text.replace("人民币", "")
    text = text.replace("USD", "")
    text = text.replace("RMB", "")
    text = text.replace("$", "")
    text = text.replace("￥", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_generated_at(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "待填":
        return "待填"
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _format_percent_or_text(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%"
    return str(value)


def _market_size_value_text(value: object, currency_code: str) -> str:
    text = _normalize_money_text(value, currency_code)
    if not isinstance(value, str):
        return text
    match = re.search(r"市场月均销售额\s*([^；;]+)", text)
    if match:
        return match.group(1).strip()
    return text


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "--", "待填"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _safe_sheet_name(name: str) -> str:
    invalid_chars = set("[]:*?/\\")
    safe = "".join("_" if char in invalid_chars else char for char in name)
    return safe[:31] or "Sheet"


def _compact_title(value: object, limit: int = 72) -> str:
    text = str(value or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _trim_sentence_end(value: object) -> str:
    return str(value).rstrip("。；; ")


def _join_or_default(values: object, default: str) -> str:
    if not values:
        return default
    if isinstance(values, (list, tuple, set)):
        text = "、".join(str(item) for item in values if str(item).strip())
        return text or default
    text = str(values).strip()
    return text or default


def _localized_title(title: str) -> str:
    return str(title or "").strip()


def _clean_display_title(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "调研看板"
    internal_markers = [
        "UI重构预览",
        "UI 重构预览",
        "UI重构版",
        "UI 重构版",
        "重构预览",
        "预览版",
        "重新验证",
        "重新驗證",
    ]
    for marker in internal_markers:
        text = text.replace(marker, "")
    text = re.sub(r"[_｜|/\\-]+\s*/", " /", text)
    text = re.sub(r"[_｜|/\\-]{2,}", "_", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.strip(" _-/｜|\\")
    return text or "调研看板"


def _display_dashboard_value(value: Any) -> str:
    if value is None:
        return "待填"
    if isinstance(value, float):
        if 0 <= value <= 1:
            return _format_percent_or_text(value)
        return _format_number(value)
    if isinstance(value, int):
        return _format_number(value)
    return str(value)


def _format_evidence_refs(evidence_refs: object) -> str:
    if not isinstance(evidence_refs, list):
        return ""
    parts: list[str] = []
    for item in evidence_refs[:6]:
        if not isinstance(item, dict):
            continue
        ref_type = str(item.get("ref_type", "")).strip()
        ref_id = str(item.get("ref_id", "")).strip()
        note = str(item.get("note", "")).strip()
        label = "/".join(part for part in (ref_type, ref_id) if part)
        if note:
            label = f"{label}({note})" if label else note
        if label:
            parts.append(label)
    return "；".join(parts)
