from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


RECOMMENDED_SOURCE_TYPES = (
    "seller_sprite_market_analysis",
    "seller_sprite_search_results",
    "seller_sprite_reverse_asin_keywords",
    "amazon_aba_keywords",
)

STAGE_ORDER = (
    "stage_0_intent",
    "stage_1_quick_probe",
    "stage_2_seller_sprite_request",
    "stage_3_data_inventory",
    "stage_4_candidate_pool",
    "stage_5_route_calibration",
    "stage_5_1_route_sorftime_calibration",
    "stage_6_voc",
    "stage_7_integrated_precheck",
    "stage_8_final_decision",
)


def audit_run_status(run_dir: Path | str, analysis_packet: dict[str, Any] | None = None) -> dict[str, Any]:
    run_path = Path(run_dir).expanduser().resolve()
    workflow_state = load_json(run_path / "workflow_state.json")
    manifest = load_json(run_path / "import_manifest.json")
    candidate_pool = load_json(run_path / "candidate_pool.json")
    research_package = load_json(run_path / "research_package.json")
    if analysis_packet is None:
        analysis_packet = load_json(run_path / "analysis" / "analysis_evidence_packet.json")

    artifacts = build_artifact_status(run_path)
    source_quality = build_source_quality(manifest)
    stage_checks = build_stage_checks(run_path, workflow_state, manifest, artifacts, analysis_packet)
    current_stage = infer_current_stage(workflow_state, stage_checks)
    blockers = build_blockers(workflow_state, source_quality, stage_checks)
    mixed_pool_checks = build_mixed_pool_checks(workflow_state, candidate_pool, research_package, analysis_packet)
    citation_checks = build_citation_checks(candidate_pool, research_package, analysis_packet)
    auto_dispatch = build_auto_dispatch_status(artifacts, workflow_state, analysis_packet)
    next_actions = build_next_actions(workflow_state, blockers, stage_checks)

    return {
        "audit_version": 1,
        "run_dir": str(run_path),
        "run_id": run_path.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_stage": current_stage,
        "stage_checks": stage_checks,
        "blockers": blockers,
        "next_actions": next_actions,
        "source_quality": source_quality,
        "mixed_pool_checks": mixed_pool_checks,
        "citation_checks": citation_checks,
        "auto_dispatch": auto_dispatch,
        "artifact_status": artifacts,
        "summary": build_summary(current_stage, blockers, next_actions),
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_artifact_status(run_dir: Path) -> dict[str, dict[str, Any]]:
    paths = {
        "workflow_state": run_dir / "workflow_state.json",
        "import_manifest": run_dir / "import_manifest.json",
        "candidate_pool": run_dir / "candidate_pool.json",
        "research_package": run_dir / "research_package.json",
        "stage5_1_sorftime_calibration": run_dir / "mcp" / "route_sorftime_calibration.json",
        "review_asin_batch": run_dir / "review_asin_batch.json",
        "review_voc_packet": run_dir / "review_voc" / "voc_evidence_packet.json",
        "search_demand_packet": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "search_demand_subagent_review": run_dir / "search_demand" / "search_demand_subagent_review.json",
        "market_structure_packet": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "analysis_packet": run_dir / "analysis" / "analysis_evidence_packet.json",
        "analysis_html": run_dir / "analysis" / "analysis_report.html",
        "analysis_xlsx": run_dir / "analysis" / "analysis_report.xlsx",
        "delivery_qa": run_dir / "analysis" / "delivery_qa_result.json",
    }
    return {
        name: {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
        for name, path in paths.items()
    }


def build_source_quality(manifest: dict[str, Any]) -> dict[str, Any]:
    data_quality = manifest.get("data_quality") if isinstance(manifest.get("data_quality"), dict) else {}
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    available = [str(item) for item in data_quality.get("available_source_types", [])]
    missing = [source for source in RECOMMENDED_SOURCE_TYPES if source not in available]
    parsed_count = sum(1 for item in files if isinstance(item, dict) and item.get("parse_status") == "parsed")
    warning_rows = []
    for item in files:
        if not isinstance(item, dict):
            continue
        for warning in item.get("warnings", []) if isinstance(item.get("warnings"), list) else []:
            warning_rows.append(
                {
                    "file": item.get("file_name", ""),
                    "warning": str(warning),
                    "severity": "warning",
                    "next_step": "确认该文件字段、站点、月份或导出范围是否符合本轮数据角色。",
                }
            )
    for source in data_quality.get("missing_source_types", []) if isinstance(data_quality.get("missing_source_types"), list) else []:
        warning_rows.append(
            {
                "file": "",
                "warning": f"缺少建议数据源：{source}",
                "severity": "warning",
                "next_step": "如果该数据源影响当前判断，补导或在报告中标为系统侧待补。",
            }
        )
    level = "good"
    if missing or warning_rows:
        level = "watch"
    if len(available) < 2:
        level = "blocked"
    return {
        "level": level,
        "file_count": len(files),
        "parsed_file_count": parsed_count,
        "available_source_types": available,
        "missing_recommended_source_types": missing,
        "warnings": warning_rows[:30],
        "next_step": source_quality_next_step(level, missing),
    }


def source_quality_next_step(level: str, missing: list[str]) -> str:
    if level == "blocked":
        return "先补齐至少两个有效数据源，否则不要进入正式分析。"
    if missing:
        return "优先确认缺失数据源是否影响本轮判断；影响核心结论时补导，不影响时在报告中标为数据边界。"
    return "数据源结构可继续使用，进入下一阶段证据交叉。"


def build_stage_checks(
    run_dir: Path,
    workflow_state: dict[str, Any],
    manifest: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    analysis_packet: dict[str, Any],
) -> list[dict[str, Any]]:
    data_quality = manifest.get("data_quality") if isinstance(manifest.get("data_quality"), dict) else {}
    available = data_quality.get("available_source_types") if isinstance(data_quality.get("available_source_types"), list) else []
    next_actions = workflow_state.get("next_actions") if isinstance(workflow_state.get("next_actions"), list) else []
    return [
        stage_check("stage_0_intent", bool(workflow_state.get("initial_intent")), "用户约束和初始意图已记录", "补齐场景、站点、禁区和偏好。"),
        stage_check("stage_1_quick_probe", bool((workflow_state.get("known_inputs") or {}).get("stage1_quick_probe_summary")), "快探摘要已记录", "补 Sorftime 快探摘要、候选 ASIN 和候选类目。"),
        stage_check("stage_2_seller_sprite_request", bool(available), "卖家精灵导入清单已解析", "按完整导出清单补卖家精灵文件。"),
        stage_check("stage_3_data_inventory", bool(manifest.get("files")), "数据盘点已生成 import_manifest", "运行 inspect_manual_exports 生成 manifest。"),
        stage_check("stage_4_candidate_pool", artifacts["candidate_pool"]["exists"], "候选池已生成", "运行 build_candidate_pool_from_import_manifest。"),
        stage_check("stage_5_route_calibration", artifacts["review_asin_batch"]["exists"] or artifacts["research_package"]["exists"], "路线矩阵/评论 ASIN 批次已形成", "输出路线矩阵、代表 ASIN 和 VOC 批次。"),
        stage_check("stage_5_1_route_sorftime_calibration", artifacts["stage5_1_sorftime_calibration"]["exists"], "评论前轻量 Sorftime 校准已完成", "补 route_sorftime_calibration.json。"),
        stage_check("stage_6_voc", artifacts["review_voc_packet"]["exists"], "评论 VOC evidence 已生成", "等待评论插件导出并运行 VOC 构建脚本。", pending_hint=bool(next_actions)),
        stage_check("stage_7_integrated_precheck", artifacts["analysis_packet"]["exists"] and bool(analysis_packet.get("category_selection_derivation")), "Stage 7 市场预审报告 evidence 已生成", "补齐 Search/Market/VOC evidence 后生成市场预审报告。"),
        stage_check("stage_8_final_decision", str(workflow_state.get("stage", "")).startswith("stage_8") or str(workflow_state.get("stage", "")).startswith("final"), "最终市场判断已记录", "基于大类/小类市场分析、关键词边界和 VOC 证据输出继续看/谨慎继续/暂缓。"),
    ]


def stage_check(stage: str, passed: bool, ok_note: str, next_step: str, pending_hint: bool = False) -> dict[str, Any]:
    if passed:
        status = "completed"
    elif pending_hint:
        status = "pending"
    else:
        status = "blocked" if stage in {"stage_2_seller_sprite_request", "stage_3_data_inventory", "stage_6_voc"} else "pending"
    return {
        "stage": stage,
        "status": status,
        "evidence": ok_note if passed else "",
        "next_step": "" if passed else next_step,
    }


def infer_current_stage(workflow_state: dict[str, Any], stage_checks: list[dict[str, Any]]) -> dict[str, Any]:
    explicit = str(workflow_state.get("stage") or "")
    for check in stage_checks:
        if check["status"] != "completed":
            return {
                "stage": explicit or check["stage"],
                "status": check["status"],
                "label": stage_label(explicit or check["stage"]),
                "next_step": check["next_step"],
            }
    return {
        "stage": explicit or "stage_9_final_decision",
        "status": "completed",
        "label": stage_label(explicit or "stage_9_final_decision"),
        "next_step": "本轮阶段检查均已完成，可进入最终复核或归档。",
    }


def stage_label(stage: str) -> str:
    labels = {
        "stage_0_intent": "Stage 0 意图收集",
        "stage_1_quick_probe": "Stage 1 候选快探",
        "stage_2_seller_sprite_request": "Stage 2 卖家精灵导出",
        "stage_3_data_inventory": "Stage 3 数据盘点",
        "stage_4_candidate_pool": "Stage 4 候选池",
        "stage_5_route_calibration": "Stage 5 路线矩阵",
        "stage_5_1_route_sorftime_calibration": "Stage 5.1 轻量 Sorftime 校准",
        "stage_5_1_route_sorftime_calibration_completed": "Stage 5.1 已完成，等待评论",
        "stage_6_voc": "Stage 6 评论 VOC",
        "stage_7_integrated_precheck": "Stage 7 综合预审",
        "stage_8_final_decision": "Stage 8 最终市场判断",
    }
    return labels.get(stage, stage or "未知阶段")


def build_blockers(
    workflow_state: dict[str, Any],
    source_quality: dict[str, Any],
    stage_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for item in workflow_state.get("missing_inputs", []) if isinstance(workflow_state.get("missing_inputs"), list) else []:
        blockers.append(
            {
                "type": "missing_input",
                "severity": "blocking",
                "item": str(item),
                "impact": "该输入缺失会阻止对应阶段进入正式分析。",
                "next_step": next_step_for_missing_input(str(item)),
                "source": "workflow_state.missing_inputs",
            }
        )
    if source_quality.get("level") == "blocked":
        blockers.append(
            {
                "type": "data_quality",
                "severity": "blocking",
                "item": "有效数据源不足",
                "impact": "无法做多源交叉，容易把单一数据当结论。",
                "next_step": source_quality.get("next_step", ""),
                "source": "import_manifest.data_quality",
            }
        )
    for check in stage_checks:
        if check["status"] == "blocked":
            blockers.append(
                {
                    "type": "stage_blocker",
                    "severity": "blocking",
                    "item": stage_label(check["stage"]),
                    "impact": "该阶段未完成，后续报告只能作为观察或待补。",
                    "next_step": check["next_step"],
                    "source": check["stage"],
                }
            )
    return blockers[:20]


def next_step_for_missing_input(item: str) -> str:
    text = item.lower()
    if "评论" in item or "review" in text or "voc" in text:
        return "等待评论插件导出，将 Excel/HTML 放入 inputs/reviews 后运行 VOC 构建脚本。"
    if "小类" in item or "category" in text:
        return "补齐小类 Top100、代表 ASIN 和关键词自然位验证。"
    return "补齐该输入或在报告中标明系统侧待补。"


def build_mixed_pool_checks(
    workflow_state: dict[str, Any],
    candidate_pool: dict[str, Any],
    research_package: dict[str, Any],
    analysis_packet: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    boundary = str((workflow_state.get("known_inputs") or {}).get("confirmed_boundary") or "")
    if boundary:
        checks.append(
            {
                "source": "workflow_state.known_inputs.confirmed_boundary",
                "risk_type": "boundary_exclusion",
                "status": "recorded",
                "evidence": boundary,
                "next_step": "报告中继续保留这些排除项，防止后续候选池重新混入。",
            }
        )
    for candidate in candidate_pool.get("candidates", []) if isinstance(candidate_pool.get("candidates"), list) else []:
        for item in candidate.get("excluded_or_watch_items", []) if isinstance(candidate.get("excluded_or_watch_items"), list) else []:
            checks.append(
                {
                    "source": "candidate_pool.excluded_or_watch_items",
                    "risk_type": "candidate_exclusion",
                    "status": "recorded",
                    "evidence": public_text(item),
                    "next_step": "保留为排除或观察，不纳入主线销量/关键词判断。",
                }
            )
    mix_summary = ((analysis_packet.get("keyword_pool") or {}).get("mix_pool_summary") or {})
    if mix_summary:
        checks.append(
            {
                "source": "analysis.keyword_pool.mix_pool_summary",
                "risk_type": "keyword_mix_pool",
                "status": "scored",
                "evidence": f"高风险 {mix_summary.get('high_risk_count', 0)} 个，中风险 {mix_summary.get('medium_risk_count', 0)} 个。",
                "next_step": "高风险词只作排除/观察，不作为主市场词。",
            }
        )
    return checks[:20]


def build_citation_checks(
    candidate_pool: dict[str, Any],
    research_package: dict[str, Any],
    analysis_packet: dict[str, Any],
) -> dict[str, Any]:
    refs: list[str] = []
    refs.extend(str(item) for item in candidate_pool.get("metadata", {}).get("data_sources", []) if item)
    for candidate in candidate_pool.get("candidates", []) if isinstance(candidate_pool.get("candidates"), list) else []:
        refs.extend(str(item) for item in candidate.get("source_refs", []) if item)
    for packet in analysis_packet.get("source_packets", []) if isinstance(analysis_packet.get("source_packets"), list) else []:
        path = packet.get("path") if isinstance(packet, dict) else ""
        if path:
            refs.append(str(path))
    return {
        "source_ref_count": len(set(refs)),
        "has_category_derivation": isinstance(analysis_packet.get("category_selection_derivation"), dict) and bool(analysis_packet.get("category_selection_derivation")),
        "has_reference_asins": bool(analysis_packet.get("reference_asin_pool")),
        "has_keyword_pool": bool((analysis_packet.get("keyword_pool") or {}).get("roles")),
        "has_blocking_gaps": bool(analysis_packet.get("blocking_gaps")),
        "sample_refs": sorted(set(refs))[:12],
    }


def build_auto_dispatch_status(
    artifacts: dict[str, dict[str, Any]],
    workflow_state: dict[str, Any],
    analysis_packet: dict[str, Any],
) -> dict[str, Any]:
    required_ready = {
        "search_demand": artifacts.get("search_demand_packet", {}).get("exists", False) or bool((workflow_state.get("known_inputs") or {}).get("stage7_search_demand_evidence")),
        "market_structure": artifacts.get("market_structure_packet", {}).get("exists", False) or bool((workflow_state.get("known_inputs") or {}).get("stage7_market_structure_evidence")),
        "voc": artifacts.get("review_voc_packet", {}).get("exists", False),
    }
    dispatch_ready = all(required_ready.values())
    source_packets = analysis_packet.get("source_packets") if isinstance(analysis_packet.get("source_packets"), list) else []
    real_spawn_packets = [
        packet
        for packet in source_packets
        if isinstance(packet, dict)
        and isinstance(packet.get("execution_provenance"), dict)
        and packet["execution_provenance"].get("execution_mode") == "real_subagent_spawn"
    ]
    independent_reviews = []
    reviews = analysis_packet.get("independent_subagent_reviews") if isinstance(analysis_packet.get("independent_subagent_reviews"), dict) else {}
    for review in reviews.values():
        if (
            isinstance(review, dict)
            and review.get("agent_role")
            and review.get("subagent_id")
            and str(review.get("status") or "").lower() in {"available", "completed", "pass"}
        ):
            independent_reviews.append(review)
    if dispatch_ready and analysis_packet:
        status = "completed"
        next_step = "Stage 7 市场预审报告已生成；检查 QA 后决定继续看/谨慎继续/暂缓。"
    elif dispatch_ready:
        status = "ready_to_dispatch"
        next_step = "Search/Market/VOC evidence 已齐，默认启动 Stage 7 市场预审。"
    else:
        status = "waiting_for_market_evidence"
        next_step = "补齐 Search Demand、Market Structure 和 VOC evidence 后生成市场预审。"
    return {
        "status": status,
        "instruction_ready": True,
        "required_packets_ready": required_ready,
        "real_subagent_spawn_packet_count": len(real_spawn_packets),
        "independent_subagent_review_count": len(independent_reviews),
        "default_policy": "Stage 7 聚焦市场预审：Search Demand、Market Structure、VOC 可默认并行深扫；不能 spawn 时 serial_fallback 并记录 provenance。",
        "next_step": next_step,
    }


def build_next_actions(
    workflow_state: dict[str, Any],
    blockers: list[dict[str, Any]],
    stage_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for item in workflow_state.get("next_actions", []) if isinstance(workflow_state.get("next_actions"), list) else []:
        if not isinstance(item, dict):
            continue
        recommended = item.get("recommended_action") if isinstance(item.get("recommended_action"), dict) else {}
        actions.append(
            {
                "stage": item.get("stage", ""),
                "label": recommended.get("label") or item.get("question") or "下一步",
                "reason": recommended.get("reason") or item.get("question") or "",
                "action_type": recommended.get("type", ""),
                "source": "workflow_state.next_actions",
            }
        )
    for blocker in blockers:
        actions.append(
            {
                "stage": blocker.get("source", ""),
                "label": blocker.get("item", ""),
                "reason": blocker.get("impact", ""),
                "action_type": "unblock",
                "source": "audit.blockers",
                "next_step": blocker.get("next_step", ""),
            }
        )
    if not actions:
        pending = next((check for check in stage_checks if check["status"] != "completed"), {})
        if pending:
            actions.append(
                {
                    "stage": pending.get("stage", ""),
                    "label": stage_label(str(pending.get("stage", ""))),
                    "reason": "继续完成当前未完成阶段。",
                    "action_type": "continue_stage",
                    "source": "audit.stage_checks",
                    "next_step": pending.get("next_step", ""),
                }
            )
    return dedupe_actions(actions)[:10]


def dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for action in actions:
        key = (str(action.get("label")), str(action.get("next_step") or action.get("reason")))
        if key in seen:
            continue
        seen.add(key)
        result.append(action)
    return result


def build_summary(current_stage: dict[str, Any], blockers: list[dict[str, Any]], next_actions: list[dict[str, Any]]) -> str:
    blocker_text = f"阻塞 {len(blockers)} 项" if blockers else "暂无硬阻塞"
    next_action = next_actions[0].get("next_step") or next_actions[0].get("reason") if next_actions else "按当前阶段继续推进。"
    return f"{current_stage.get('label')} / {current_stage.get('status')}；{blocker_text}；下一步：{next_action}"


def public_text(value: Any) -> str:
    if isinstance(value, dict):
        return "；".join(f"{key}: {val}" for key, val in value.items() if val)
    if isinstance(value, list):
        return "；".join(public_text(item) for item in value if item)
    return " ".join(str(value or "").split())
