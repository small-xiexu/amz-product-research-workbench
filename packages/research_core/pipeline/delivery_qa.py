#!/usr/bin/env python3
"""Delivery QA — source_path validation, value consistency check, HTML pattern scan."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any

from packages.research_core.pipeline.constants import (
    QA_RULE_VERSION,
    FORBIDDEN_HTML_PATTERNS,
    REQUIRED_SECTION_MARKERS,
    VOC_REQUIRED_EVIDENCE_FIELDS,
    REQUIRED_REPORT_DATA_SECTIONS,
    REQUIRED_REPORT_DATA_DECLARATIONS,
)
from packages.research_core.pipeline._utils import (
    _NOT_FOUND, _split_path, _navigate,
)

def run_delivery_qa(report_data_path: Path, html_path: Path, xlsx_path: Path, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    run_dir = html_path.parent.parent
    packets = _load_packets_for_qa(run_dir, analysis)
    source_result = _validate_report_data_sources(report_data_path, packets)
    value_result = _validate_values_against_sources(report_data_path, packets)
    has_data = _report_data_has_required_sections(report_data_path)
    forbidden_result = _has_no_forbidden_html_patterns(html_path)
    checks = {
        "report_data_exists": report_data_path.exists(),
        "html_exists": html_path.exists(),
        "xlsx_exists": xlsx_path.exists(),
        "report_data_has_required_sections": has_data,
        "has_no_removed_legacy_sections": _has_no_removed_legacy_sections(html_path),
        "has_inline_style": _has_inline_style(html_path),
        "has_8_sections": _has_8_sections(html_path),
        "has_gonogo_class": _has_gonogo_class(html_path),
        "report_data_sources_valid": source_result["pass"],
        "report_data_values_consistent": value_result["pass"],
        "has_no_forbidden_html_patterns": forbidden_result["pass"],
    }
    if forbidden_result.get("hits"):
        checks["forbidden_html_hits"] = forbidden_result["hits"]
    if source_result.get("reason"):
        checks["report_data_sources_note"] = source_result["reason"]
    if value_result.get("reason"):
        checks["report_data_values_note"] = value_result["reason"]
    if value_result.get("mismatches"):
        checks["report_data_value_mismatches"] = value_result["mismatches"]
    failures = [name for name, passed in checks.items() if not passed and name not in ("report_data_sources_note", "report_data_values_note", "report_data_value_mismatches")]
    return {
        "status": "pass" if not failures else "fail",
        "qa_rule_version": QA_RULE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "checks": checks,
        "failures": failures,
    }


def _load_packets_for_qa(run_dir: Path, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load evidence packets for source_path validation.

    优先从磁盘读取 analysis_packet.json（持久化中间层）；
    若不存在则回退到入参 analysis（运行时兼容）。
    """
    paths = {
        "market_structure": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "search_demand": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "voc": run_dir / "review_voc" / "voc_evidence_packet.json",
        "route_matrix": run_dir / "route_matrix_confirm.json",
    }
    packets: dict[str, Any] = {}
    for key, path in paths.items():
        try:
            if path.exists():
                packets[key] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            pass

    # 优先从磁盘读取 analysis_packet.json，保证交付后可独立溯源
    analysis_packet_path = run_dir / "analysis" / "analysis_packet.json"
    if analysis_packet_path.exists():
        try:
            packets["analysis"] = json.loads(analysis_packet_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            if analysis:
                packets["analysis"] = analysis
    elif analysis:
        packets["analysis"] = analysis
    return packets


def _has_no_removed_legacy_sections(html_path: Path) -> bool:
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    removed_section_markers = (
        "legacy_source_collection_section",
        "legacy_fillback_stage_section",
        "legacy_cost_review_section",
    )
    return not any(marker in html for marker in removed_section_markers)


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


def _has_no_forbidden_html_patterns(html_path: Path) -> dict:
    """扫描 HTML 中的禁止模式：抽象路线标签、内部术语、虚假宣传措辞。"""
    if not html_path.exists():
        return {"pass": False, "hits": ["HTML 文件不存在"]}
    html = html_path.read_text(encoding="utf-8")
    hits = []
    for pattern, description in FORBIDDEN_HTML_PATTERNS:
        matches = re.findall(pattern, html)
        if matches:
            unique_matches = list(set(matches))[:5]
            hits.append(f"{description}（匹配: {', '.join(unique_matches)}）")
    return {"pass": len(hits) == 0, "hits": hits}


def _has_inline_style(html_path: Path) -> bool:
    """HTML 必须内嵌 <style>（内容来自 report_template.css），不能使用外部 <link>。"""
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    has_inline_style = '<style>' in html
    import re
    has_link = bool(re.search(r'<link[^>]*report_template\.css', html))
    return has_inline_style and not has_link


REQUIRED_SECTION_MARKERS = (
    "类目全景",
    "数据来源与口径",
    "核心竞品",
    "用户痛点",
    "价格带分布",
    "关键词与流量策略",
    "风险与下一步",
)


def _has_8_sections(html_path: Path) -> bool:
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    return all(marker in html for marker in REQUIRED_SECTION_MARKERS)


def _has_gonogo_class(html_path: Path) -> bool:
    if not html_path.exists():
        return False
    html = html_path.read_text(encoding="utf-8")
    return 'class="go-nogo"' in html or "class='go-nogo'" in html


VOC_REQUIRED_EVIDENCE_FIELDS = ("review_id", "quote", "rating", "asin")


def _has_voc_evidence_refs(analysis_json: Path) -> bool:
    """VOC 痛点必须有 evidence_refs，且每个 ref 包含 review_id/quote/rating/asin 四字段。"""
    if not analysis_json.exists():
        return False
    data = json.loads(analysis_json.read_text(encoding="utf-8"))
    voc = data.get("voc_spec_translation") or {}
    pain_points = voc.get("pain_points") or []
    if not pain_points:
        # 没有痛点时不扣分（可能评论样本不足）
        return True
    return all(
        isinstance(pp.get("evidence_refs"), list)
        and len(pp["evidence_refs"]) > 0
        and all(
            isinstance(ref, dict)
            and all(ref.get(field) for field in VOC_REQUIRED_EVIDENCE_FIELDS)
            for ref in pp["evidence_refs"]
        )
        for pp in pain_points
    )


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


def _report_data_has_required_sections(report_data_path: Path) -> bool:
    """report_data.json 必须包含所有必要的板块数据。"""
    if not report_data_path.exists():
        return False
    try:
        data = json.loads(report_data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return False
    return all(key in data for key in REQUIRED_REPORT_DATA_DECLARATIONS) and all(
        section in data for section in REQUIRED_REPORT_DATA_SECTIONS
    )


def _validate_report_data_sources(report_data_path: Path, packets: dict[str, Any]) -> dict:
    """校验 report_data.json 中 source_path 能否在证据包中找到对应字段。

    返回 dict 包含 pass/fail 和解析明细。阈值：
    - 存在空 source_path → block（pass=False，AI 未填充）
    - 未解析率 > 5% → block（pass=False）
    - 未解析率 > 2% → warning（pass=True，但记录）
    - 未解析率 ≤ 2% 且无空路径 → pass

    __ai_pending__ 是 seed 占位标记，表示该字段需 AI 增强后填充，记 warning 不阻断。
    """
    if not report_data_path.exists():
        return {"pass": False, "total": 0, "resolved": 0, "vague": 0, "unresolved": 0, "empty": 0, "ai_pending": 0, "unresolved_pct": 0.0, "reason": "report_data.json 不存在"}
    try:
        data = json.loads(report_data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {"pass": False, "total": 0, "resolved": 0, "vague": 0, "unresolved": 0, "empty": 0, "ai_pending": 0, "unresolved_pct": 0.0, "reason": "report_data.json 解析失败"}

    source_paths = _extract_source_paths(data)
    unresolved: list[dict] = []
    resolved = 0
    vague = 0
    empty = 0
    ai_pending = 0

    for item in source_paths:
        sp = item["source_path"].strip()
        if sp == "__ai_pending__":
            ai_pending += 1
            continue
        if not sp or sp == "N/A" or sp == "—":
            empty += 1
            unresolved.append({"path": "(空)", "key": item.get("parent_key", ""), "reason": "source_path 为空字符串，AI 未填充"})
            continue

        result = _try_resolve_path(sp, packets)
        if result["status"] == "unresolved":
            unresolved.append({"path": sp, "key": item.get("parent_key", ""), "reason": result["reason"]})
        elif result["status"] == "ok" and "模糊" in result.get("reason", ""):
            vague += 1
        else:
            resolved += 1

    total = len(source_paths)
    effective = max(total - ai_pending, 1)  # __ai_pending__ 不参与未解析率计算
    unresolved_pct = len(unresolved) / max(effective, 1)

    # 空 source_path 直接阻断
    if empty > 0:
        reason = f"存在 {empty} 条空 source_path（AI 未填充），共 {len(unresolved)}/{effective} 条路径无法解析 ({unresolved_pct:.0%})"
        if ai_pending:
            reason += f"，{ai_pending} 条标记为 __ai_pending__（待 AI 增强）"
        return {
            "pass": False,
            "total": total,
            "resolved": resolved,
            "vague": vague,
            "unresolved": len(unresolved),
            "empty": empty,
            "ai_pending": ai_pending,
            "unresolved_pct": unresolved_pct,
            "reason": reason,
            "unresolved_paths": unresolved,
        }

    passed = unresolved_pct <= 0.05
    reason_parts = []
    if unresolved_pct > 0.05:
        reason_parts.append(f"未解析率 {unresolved_pct:.0%} 超过 5% 阈值，共 {len(unresolved)}/{effective} 条路径无法溯源")
    elif unresolved_pct > 0.02:
        reason_parts.append(f"未解析率 {unresolved_pct:.0%} 在 2%-5% 之间，共 {len(unresolved)}/{effective} 条路径无法溯源（不阻断）")
    if ai_pending:
        reason_parts.append(f"{ai_pending} 条标记为 __ai_pending__（待 AI 增强）")

    return {
        "pass": passed,
        "total": total,
        "resolved": resolved,
        "vague": vague,
        "unresolved": len(unresolved),
        "empty": empty,
        "ai_pending": ai_pending,
        "unresolved_pct": unresolved_pct,
        "reason": "；".join(reason_parts) if reason_parts else "",
        "unresolved_paths": unresolved,
    }


def _extract_source_paths(obj: Any, parent_key: str = "", parent_obj: dict | None = None) -> list[dict]:
    """递归提取 report_data.json 中所有 source_path 及其上下文。

    返回值中每条记录包含 source_path、parent_key、以及同级 value 字段（用于值比对）。
    """
    results: list[dict] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "source_path" and isinstance(val, str):
                entry: dict = {"source_path": val, "parent_key": parent_key}
                # 当前对象 obj 中查找同级 value 字段（非 parent_obj）
                if "value" in obj:
                    entry["reported_value"] = obj.get("value")
                results.append(entry)
            else:
                results.extend(_extract_source_paths(val, parent_key=key, parent_obj=obj))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_extract_source_paths(item, parent_key=parent_key, parent_obj=item if isinstance(item, dict) else None))
    return results


def _try_resolve_path(source_path: str, packets: dict[str, Any]) -> dict:
    """尝试在证据包中解析一个 source_path。

    支持的路径格式：
    - packet.field.subfield (如 market_structure.market_size.primary_market)
    - packet.array_id.field (如 search_demand.f8.value.top100_monthly_units)
    - packet.array[index].field (如 voc.pain_points_by_dimension[0].review_count)
    - packet.field (模糊溯源，如 market_structure)
    """
    # 匹配包名前缀
    packet_key = None
    rest = source_path
    for pkey in ("market_structure", "search_demand", "voc", "route_matrix", "analysis", "seller_sprite"):
        if source_path.startswith(pkey):
            packet_key = pkey
            rest = source_path[len(pkey):].lstrip(".")
            break

    if not packet_key:
        return {"status": "unresolved", "reason": f"无法识别包名前缀: {source_path}"}

    # Alias: seller_sprite -> market_structure
    if packet_key == "seller_sprite":
        packet_key = "market_structure"

    packet = packets.get(packet_key)
    if not packet:
        return {"status": "unresolved", "reason": f"证据包未加载: {packet_key}"}

    if not rest:
        # 只有包名无字段路径 —— 模糊溯源
        return {"status": "ok", "reason": "包级模糊溯源（无字段路径）"}

    # 剥离结尾的描述性文字（空格后跟中文说明、加总等）
    stripped = rest
    for sep in [" 月销额加总", " 月销额:", " 月销额计算:", " 竞品数对比", " 竞品数", " 加总", " + "]:
        if sep in stripped:
            idx = stripped.index(sep)
            stripped = stripped[:idx]
            break
    # 多引用复合路径（如 facts[f8,f9,f10]）→ 无法单点解析，跳过
    if "][" in stripped or (stripped.count("[") >= 2 and "," in stripped):
        return {"status": "ok", "reason": "复合引用（多源加总），无法单点解析"}

    # 分割路径
    parts = _split_path(stripped)
    if not parts:
        return {"status": "unresolved", "reason": f"路径解析后为空: {rest}"}

    # 导航 JSON
    current: Any = packet
    for part in parts:
        current = _navigate(current, part)
        if current is _NOT_FOUND:
            return {"status": "unresolved", "reason": f"路径段 '{part}' 在 '{packet_key}' 中未找到"}

    return {"status": "ok", "reason": "已解析", "resolved_value": current}


def _validate_values_against_sources(
    report_data_path: Path, packets: dict[str, Any]
) -> dict:
    """抽查 report_data.json 中 value 与证据包实际值是否一致。

    对每条已解析的 source_path，提取证据包中的字段值，做归一化比对。
    返回 mismatches 列表和 pass/fail。
    """
    if not report_data_path.exists():
        return {"pass": True, "mismatches": [], "checked": 0, "skipped": 0}

    try:
        data = json.loads(report_data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {"pass": True, "mismatches": [], "checked": 0, "skipped": 0}

    source_paths = _extract_source_paths(data)
    checked = 0
    skipped = 0
    mismatches: list[dict] = []

    for item in source_paths:
        sp = item["source_path"].strip()
        reported = item.get("reported_value")

        # 跳过占位符和空值
        if not sp or sp in ("N/A", "—", "__ai_pending__"):
            skipped += 1
            continue
        if reported is None or str(reported).strip() in ("", "待补", "—"):
            skipped += 1
            continue

        result = _try_resolve_path(sp, packets)
        if result["status"] != "ok" or "模糊" in result.get("reason", ""):
            skipped += 1
            continue

        resolved = result.get("resolved_value")
        if resolved is None:
            skipped += 1
            continue

        # 解析到 dict/list：派生值（如 recommended_price、core_search_volume），
        # 无法做标量比对，但至少验证源数据非空、派生依据存在。
        if isinstance(resolved, (dict, list)):
            if _is_empty(resolved):
                mismatches.append({
                    "path": sp,
                    "key": item.get("parent_key", ""),
                    "reported": str(reported),
                    "resolved": "∅ (空 dict/list，派生值缺少依据)",
                })
            checked += 1
            continue

        if not _values_match(reported, resolved):
            mismatches.append({
                "path": sp,
                "key": item.get("parent_key", ""),
                "reported": str(reported),
                "resolved": str(resolved),
            })

        checked += 1

    passed = len(mismatches) == 0
    reason = ""
    if mismatches:
        reason = f"{len(mismatches)}/{checked} 条抽查值与证据包不一致"
    elif checked > 0:
        reason = f"抽查 {checked} 条，全部一致"

    return {
        "pass": passed,
        "checked": checked,
        "skipped": skipped,
        "mismatches": mismatches,
        "reason": reason,
    }


def _is_empty(val: Any) -> bool:
    """判断值是否为空的 dict/list（派生值缺少依据）。"""
    if isinstance(val, dict):
        return len(val) == 0
    if isinstance(val, list):
        return len(val) == 0
    return False


def _values_match(reported: Any, resolved: Any) -> bool:
    """归一化比较两个值是否匹配。

    处理常见的表示差异：单位后缀、货币符号、百分比格式、逗号分隔、
    绝对路径 vs 相对路径等。
    """
    if reported == resolved:
        return True

    rpt = str(reported).strip()
    rsl = str(resolved).strip()

    # 路径值：取共同的尾部（如 runs/.../file.json）比对
    if ("/" in rpt or "\\" in rpt) and ("/" in rsl or "\\" in rsl):
        rpt_parts = rpt.replace("\\", "/").rstrip("/").split("/")
        rsl_parts = rsl.replace("\\", "/").rstrip("/").split("/")
        # 取较短路径的后 N 段，在较长路径中匹配
        min_len = min(len(rpt_parts), len(rsl_parts))
        if rpt_parts[-min_len:] == rsl_parts[-min_len:]:
            return True

    def _normalize(v: Any) -> str:
        s = str(v).strip().lower()
        s = s.replace("$", "").replace(",", "").replace(" ", "")
        for suffix in ("units", "unit", "%", "usd", "cny"):
            if s.endswith(suffix):
                s = s[:-len(suffix)]
        return s.strip()

    return _normalize(reported) == _normalize(resolved)

