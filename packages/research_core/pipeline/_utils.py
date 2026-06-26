#!/usr/bin/env python3
"""Shared utility functions for the research pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.pipeline.constants import (
    REPORT_VERDICT_LABELS, ALLOWED_VERDICTS,
)

def _contract_verdict(verdict: Any) -> str:
    """将内部短判词映射为 report_data.json 契约判词。"""
    text = str(verdict or "").strip()
    if text in REPORT_VERDICT_LABELS:
        return REPORT_VERDICT_LABELS[text]
    if text in ALLOWED_VERDICTS:
        return text
    return "建议补齐数据后再评估"


def _lead_analysis(one_sentence: str, raw_verdict: Any, contract_verdict: str) -> str:
    text = str(one_sentence or "").strip()
    raw = str(raw_verdict or "").strip()
    if raw and text.startswith(raw):
        return contract_verdict + text[len(raw):]
    if text:
        return text
    return f"{contract_verdict}：市场、搜索、VOC 和供应链证据仍需补齐后再形成强结论。"


def _report_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _source_packet_ref(row: dict[str, Any], index: int) -> dict[str, Any]:
    base = f"analysis.source_packets[{index}]"
    return {
        "name": {"value": row.get("name", ""), "source_path": f"{base}.name"},
        "path": {"value": row.get("path", ""), "source_path": f"{base}.path"},
        "exists": {"value": row.get("exists", False), "source_path": f"{base}.exists"},
        "packet_id": {"value": row.get("packet_id", ""), "source_path": f"{base}.packet_id"},
        "confidence": {"value": row.get("confidence", ""), "source_path": f"{base}.confidence"},
        "execution_mode": {"value": row.get("execution_mode", ""), "source_path": f"{base}.execution_mode"},
        "provenance_note": {"value": row.get("provenance_note", ""), "source_path": f"{base}.provenance_note"},
    }


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data

_NOT_FOUND = object()


def _split_path(path: str) -> list[str]:
    """将点分隔的路径拆分为段，处理数组索引。"""
    parts: list[str] = []
    for segment in path.split("."):
        segment = segment.strip()
        if not segment:
            continue
        # 处理 array[index] 格式
        if "[" in segment and "]" in segment:
            base = segment[: segment.index("[")]
            idx_str = segment[segment.index("[") + 1 : segment.index("]")]
            if base:
                parts.append(base)
            parts.append(f"[{idx_str}]")
        else:
            parts.append(segment)
    return parts


def _navigate(current: Any, part: str) -> Any:
    """在 JSON 结构中导航一个路径段。"""
    if current is _NOT_FOUND:
        return _NOT_FOUND

    # 数组索引: [0], [1], 或 id 查找: [f2], [biothane]
    if part.startswith("[") and part.endswith("]"):
        idx_str = part[1:-1]
        if isinstance(current, list):
            try:
                idx = int(idx_str)
                if 0 <= idx < len(current):
                    return current[idx]
            except ValueError:
                pass
            for item in current:
                if isinstance(item, dict):
                    if item.get("id") == idx_str or item.get("name") == idx_str or item.get("keyword") == idx_str:
                        return item
        if isinstance(current, dict):
            for key, val in current.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict) and item.get("id") == idx_str:
                            return item
        return _NOT_FOUND

    # 对象键查找（先精确匹配）
    if isinstance(current, dict):
        if part in current:
            return current[part]
        for key in current:
            if part in key:
                return current[key]
        for key, val in current.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and item.get("id") == part:
                        return item
            elif isinstance(val, dict) and part in val:
                return val[part]

    # facts 数组按 id 查找（如 f8, f2, f10）
    if isinstance(current, list) and part.startswith("f") and len(part) <= 4:
        for item in current:
            if isinstance(item, dict) and item.get("id") == part:
                return item

    # 通用数组按 id、name、keyword 或 dimension 查找
    if isinstance(current, list):
        for item in current:
            if isinstance(item, dict):
                if item.get("id") == part or item.get("name") == part or item.get("keyword") == part or item.get("dimension") == part:
                    return item
        for item in current:
            if isinstance(item, dict):
                for key, val in item.items():
                    if isinstance(val, dict) and part in val:
                        return val[part]

    return _NOT_FOUND


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if not isinstance(value, (str, list, dict)) and value:
            return str(value)
    return ""


def first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def compact_list(values: list[Any]) -> list[str]:
    return [text for text in (public_text(value) for value in values) if text]


def join_text(value: Any, sep: str = "；") -> str:
    if isinstance(value, list):
        return sep.join(public_text(item) for item in value if public_text(item))
    if isinstance(value, dict):
        return sep.join(f"{key}: {public_text(val)}" for key, val in value.items() if public_text(val))
    return public_text(value)


def public_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return join_text(value)
    if isinstance(value, dict):
        return join_text(value)
    return str(value).strip()


def first_row_text(rows: list[Any], key: str) -> str:
    for row in rows:
        if isinstance(row, dict) and row.get(key):
            return str(row.get(key))
    return ""


def numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.replace(",", "").replace("%", "").strip()
        try:
            number = float(text)
        except ValueError:
            return None
        if "%" in value:
            return number / 100
        return number
    return None


def fmt_number(value: Any) -> str:
    number = numeric_value(value)
    if number is None:
        return str(value or "待补")
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def fmt_percent(value: Any) -> str:
    number = numeric_value(value)
    if number is None:
        return str(value or "待补")
    if abs(number) <= 1:
        number *= 100
    return f"{number:.1f}%"


def dedupe_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in rows:
        marker = str(row.get(key, "")).strip()
        if marker and marker in seen:
            continue
        if marker:
            seen.add(marker)
        result.append(row)
    return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unique_texts(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = first_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _run_id(workflow_state: dict[str, Any], run_path: Path | None = None) -> str:
    wid = first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"))
    if wid:
        return wid
    if run_path:
        return run_path.name
    return "unknown"


def _relative_path(target: Path, base: Path) -> str:
    try:
        return str(target.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(target)


def _base_tool_name(value: Any) -> str:
    text = first_text(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if "__" in text:
        text = text.rsplit("__", 1)[-1]
    return text or "unknown_tool"


def _normalize_tool_status(value: Any) -> str:
    text = first_text(value).lower()
    if "fail" in text or "error" in text:
        return "error"
    if "empty" in text:
        return "empty"
    return "success"


def _dedupe_dicts(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _case_insensitive_get(data: dict[str, Any], field: str) -> Any:
    if field in data:
        return data[field]
    folded = field.casefold()
    for key, value in data.items():
        if str(key).casefold() == folded:
            return value
    return None


def _nested_first(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _first_field(rows: list[dict[str, Any]], field: str) -> Any:
    for row in rows:
        value = _case_insensitive_get(row, field)
        if value not in (None, "", []):
            return value
    return None


def _first_metric_value(normalized: dict[str, Any]) -> Any:
    numeric_values = normalized.get("numeric_values") if isinstance(normalized, dict) else {}
    if isinstance(numeric_values, dict) and numeric_values:
        return next(iter(numeric_values.values()))
    field_values = normalized.get("field_values") if isinstance(normalized, dict) else {}
    if isinstance(field_values, dict) and field_values:
        return next(iter(field_values.values()))
    return None


def _probe_raw_result(record: dict[str, Any]) -> Any:
    for key in ("raw_result_sample", "raw_result", "response", "data"):
        if key in record and record.get(key) not in (None, "", []):
            return record.get(key)
    return None


def _result_payload(result: dict[str, Any]) -> Any:
    if not isinstance(result, dict):
        return {}
    for key in ("raw_result", "normalized_preview"):
        if key in result and result.get(key) not in (None, "", []):
            return result.get(key)
    return {}


def _call_params_for_result(snapshot: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    call_id = result.get("call_id") if isinstance(result, dict) else ""
    for call in as_list(snapshot.get("tool_calls")):
        if isinstance(call, dict) and call.get("call_id") == call_id and isinstance(call.get("params"), dict):
            return call["params"]
    return {}


def _packet_confidence(data_gaps: list[Any]) -> str:
    severe_count = sum(1 for gap in data_gaps if isinstance(gap, dict) and gap.get("type") in {"tool_result_unavailable", "tool_call_failed"})
    if severe_count >= 2:
        return "low"
    if data_gaps:
        return "medium"
    return "high"


def _field_gaps(
    spec: dict[str, Any],
    result: dict[str, Any],
    rows: list[dict[str, Any]],
    normalized: dict[str, Any],
    result_ref: str,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    tool_name = _base_tool_name(result.get("tool_name") if isinstance(result, dict) else "")
    status = result.get("status") if isinstance(result, dict) else "missing"
    if status in {"error", "empty", "missing"}:
        gaps.append(
            {
                "type": "tool_result_unavailable",
                "tool_name": tool_name or first_text(spec["tools"][0]),
                "evidence_type": spec["item_type"],
                "severity": "warning",
                "evidence_ref": result_ref,
            }
        )
    if not rows:
        gaps.append(
            {
                "type": "empty_tool_result",
                "tool_name": tool_name or first_text(spec["tools"][0]),
                "evidence_type": spec["item_type"],
                "severity": "warning",
                "evidence_ref": result_ref,
            }
        )
    present = set((normalized.get("field_values") or {}).keys())
    missing = [field for field in spec["expected_fields"] if field not in present]
    if missing:
        gaps.append(
            {
                "type": "empty_or_missing_fields",
                "tool_name": tool_name or first_text(spec["tools"][0]),
                "evidence_type": spec["item_type"],
                "fields": missing,
                "severity": "warning",
                "evidence_ref": result_ref,
            }
        )
    return gaps


def _validate_artifacts(run_path: Path, artifacts: list[str], error_cls: type[Exception]) -> None:
    for artifact in artifacts:
        p = run_path / artifact
        if not p.exists():
            raise error_cls(f"required input not found: {artifact}")

