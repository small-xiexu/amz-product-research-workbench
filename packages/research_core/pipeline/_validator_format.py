"""校验器错误结构化输出。

所有 validator 使用统一的错误格式，便于：
  1. 人类阅读：清晰展示问题位置、期望值、修复建议
  2. Agent 消费：可解析的结构化错误，直接定位合约文件和修复方向
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidatorError:
    """单个校验错误的结构化描述。"""

    code: str  # 错误码，如 "MISSING_FIELD", "TYPE_ERROR", "VALUE_RANGE"
    field_path: str  # 字段路径，如 "evidence_items[2].facts"
    message: str  # 人类可读的错误说明
    expected: str | None = None  # 期望值/类型
    actual: str | None = None  # 实际值/类型
    contract_ref: str | None = None  # 合约文件和章节
    fix_hint: str | None = None  # 修复建议
    severity: str = "ERROR"  # ERROR | WARN

    def to_dict(self) -> dict[str, Any]:
        d = {
            "code": self.code,
            "field_path": self.field_path,
            "message": self.message,
            "severity": self.severity,
        }
        if self.expected:
            d["expected"] = self.expected
        if self.actual:
            d["actual"] = self.actual
        if self.contract_ref:
            d["contract_ref"] = self.contract_ref
        if self.fix_hint:
            d["fix_hint"] = self.fix_hint
        return d


def format_human(errors: list[ValidatorError]) -> str:
    """格式化错误列表为人类可读的文本输出。"""
    if not errors:
        return ""

    lines = []
    for i, e in enumerate(errors, 1):
        lines.append(f"  [{e.severity}] #{i} {e.code}: {e.field_path}")
        lines.append(f"         {e.message}")
        if e.expected:
            lines.append(f"         期望: {e.expected}")
        if e.actual:
            lines.append(f"         实际: {e.actual}")
        if e.contract_ref:
            lines.append(f"         合约: {e.contract_ref}")
        if e.fix_hint:
            lines.append(f"         修复: {e.fix_hint}")
    return "\n".join(lines)


def format_agent_replay(errors: list[ValidatorError], stage_name: str) -> str:
    """生成可直接回放给 Agent 的修复指令文本。

    输出格式为 Markdown，Agent 可以直接逐条执行修复。
    """
    if not errors:
        return ""

    error_count = len(errors)
    blocking = [e for e in errors if e.severity == "ERROR"]
    warnings = [e for e in errors if e.severity == "WARN"]

    lines = [
        f"## 校验失败 — {stage_name}",
        f"",
        f"共 {error_count} 个问题（{len(blocking)} ERROR + {len(warnings)} WARN），必须修复后重新校验。",
        f"",
    ]

    if blocking:
        lines.append("### 阻断项（必须修复）")
        lines.append("")
        for i, e in enumerate(blocking, 1):
            lines.append(f"**{i}. [{e.code}] `{e.field_path}`**")
            lines.append(f"> {e.message}")
            if e.expected:
                lines.append(f"- 期望值：`{e.expected}`")
            if e.actual:
                lines.append(f"- 当前值：`{e.actual}`")
            if e.contract_ref:
                lines.append(f"- 合约文件：`{e.contract_ref}`")
            if e.fix_hint:
                lines.append(f"- 修复方法：{e.fix_hint}")
            lines.append("")

    if warnings:
        lines.append("### 警告项（建议修复）")
        lines.append("")
        for i, e in enumerate(warnings, 1):
            lines.append(f"**{i}. [{e.code}] `{e.field_path}`**")
            lines.append(f"> {e.message}")
            if e.fix_hint:
                lines.append(f"- 建议：{e.fix_hint}")
            lines.append("")

    return "\n".join(lines)


def format_json(errors: list[ValidatorError]) -> str:
    """输出 JSON 格式的结构化错误（供脚本间通信）。"""
    return json.dumps(
        {"status": "FAIL", "error_count": len(errors), "errors": [e.to_dict() for e in errors]},
        ensure_ascii=False,
        indent=2,
    )
