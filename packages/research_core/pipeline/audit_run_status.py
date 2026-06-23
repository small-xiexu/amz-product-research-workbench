from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


STAGE_ORDER = (
    "stage_1_inputs",
    "stage_4_candidate_pool",
    "stage_5_route_calibration",
    "stage_6_voc",
    "stage_7_analysis",
)


def audit_run_status(run_dir: Path | str) -> dict[str, Any]:
    run_path = Path(run_dir).expanduser().resolve()
    candidate_pool = load_json(run_path / "candidate_pool.json")
    route_matrix = load_json(run_path / "route_matrix_confirm.json")
    report_data = load_json(run_path / "analysis" / "report_data.json")
    qa_result = load_json(run_path / "analysis" / "delivery_qa_result.json")

    artifacts = build_artifact_status(run_path)
    source_quality = build_source_quality(run_path)
    stage_checks = build_stage_checks(artifacts, report_data, qa_result)
    current_stage = infer_current_stage(stage_checks)
    blockers = build_blockers(source_quality, stage_checks, qa_result, artifacts)
    next_actions = build_next_actions(blockers, stage_checks)

    return {
        "audit_version": 2,
        "run_dir": str(run_path),
        "run_id": run_path.name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_stage": current_stage,
        "stage_checks": stage_checks,
        "blockers": blockers,
        "next_actions": next_actions,
        "source_quality": source_quality,
        "artifact_status": artifacts,
        "summary": build_summary(current_stage, blockers, next_actions),
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _find_analysis_file(run_dir: Path, suffix: str) -> Path:
    analysis_dir = run_dir / "analysis"
    if analysis_dir.exists():
        for f in analysis_dir.iterdir():
            if f.is_file() and f.name.endswith(suffix):
                return f
    product = re.sub(r'^\d{8}_', '', run_dir.name)
    return analysis_dir / f"{product}{suffix}"


def build_artifact_status(run_dir: Path) -> dict[str, dict[str, Any]]:
    paths = {
        "candidate_pool": run_dir / "candidate_pool.json",
        "route_matrix_confirm": run_dir / "route_matrix_confirm.json",
        "market_structure_packet": run_dir / "market_structure" / "market_structure_evidence_packet.json",
        "search_demand_packet": run_dir / "search_demand" / "search_demand_evidence_packet.json",
        "review_voc_packet": run_dir / "review_voc" / "voc_evidence_packet.json",
        "sorftime_verification": run_dir / "mcp" / "sorftime_verification.json",
        "analysis_report_data": run_dir / "analysis" / "report_data.json",
        "analysis_html": _find_analysis_file(run_dir, "_分析报告.html"),
        "analysis_xlsx": _find_analysis_file(run_dir, "_数据回表.xlsx"),
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


def build_source_quality(run_dir: Path) -> dict[str, Any]:
    inputs_dir = run_dir / "inputs"
    seller_sprite_count = 0
    reviews_count = 0
    if inputs_dir.exists():
        ss_dir = inputs_dir / "seller_sprite"
        rv_dir = inputs_dir / "reviews"
        seller_sprite_count = len(list(ss_dir.glob("*.xlsx"))) + len(list(ss_dir.glob("*.xls"))) if ss_dir.exists() else 0
        reviews_count = len(list(rv_dir.glob("*.xlsx"))) + len(list(rv_dir.glob("*.xls"))) if rv_dir.exists() else 0

    sources = []
    if seller_sprite_count > 0:
        sources.append(f"卖家精灵 ({seller_sprite_count} 文件)")
    if reviews_count > 0:
        sources.append(f"评论 ({reviews_count} 文件)")

    mcp_dir = run_dir / "mcp"
    if mcp_dir.exists() and list(mcp_dir.glob("*.json")):
        sources.append("Sorftime MCP")

    level = "good" if len(sources) >= 2 else ("watch" if len(sources) >= 1 else "blocked")
    return {
        "level": level,
        "sources": sources,
        "seller_sprite_file_count": seller_sprite_count,
        "reviews_file_count": reviews_count,
        "next_step": (
            "数据源充足，可进入分析阶段。"
            if level == "good"
            else "建议补齐至少两个数据源（卖家精灵 + 评论/Sorftime）。"
            if level == "watch"
            else "缺少数据源，请先导入卖家精灵或评论文件。"
        ),
    }


def build_stage_checks(
    artifacts: dict[str, dict[str, Any]],
    report_data: dict[str, Any],
    qa_result: dict[str, Any],
) -> list[dict[str, Any]]:
    has_inputs = artifacts["candidate_pool"]["exists"] or artifacts["market_structure_packet"]["exists"]
    has_candidate = artifacts["candidate_pool"]["exists"] and bool(
        (load_json(Path(artifacts["candidate_pool"]["path"]))).get("candidates")
    )
    has_route = artifacts["route_matrix_confirm"]["exists"]
    has_voc = artifacts["review_voc_packet"]["exists"]
    has_report = artifacts["analysis_report_data"]["exists"] and bool(report_data.get("hero"))
    has_html = artifacts["analysis_html"]["exists"]
    has_xlsx = artifacts["analysis_xlsx"]["exists"]
    qa_passed = qa_result.get("status") == "pass"
    stage_7_artifacts_exist = has_report and has_html and has_xlsx
    stage_7_done = stage_7_artifacts_exist and qa_passed

    if qa_passed:
        stage_7_evidence = "市场分析报告已生成并通过 QA"
    elif stage_7_artifacts_exist:
        # QA 文件缺失或未通过：artifact 存在但不满足交付标准
        qa_exists = bool(qa_result)
        stage_7_evidence = "市场分析报告已生成（QA 未通过）" if qa_exists else "市场分析报告已生成（QA 未执行，请运行 build_analysis_report.py）"
    else:
        stage_7_evidence = ""

    return [
        stage_check(
            "stage_1_inputs",
            artifacts["market_structure_packet"]["exists"] or artifacts["search_demand_packet"]["exists"] or bool(has_inputs),
            "输入数据已就位（卖家精灵/评论/Sorftime）",
            "请运营导出数据到 inputs/seller_sprite 或 inputs/reviews。",
        ),
        stage_check(
            "stage_4_candidate_pool",
            artifacts["candidate_pool"]["exists"],
            "候选品池已生成",
            "运行候选池构建或 AI 交互生成候选。",
        ),
        stage_check(
            "stage_5_route_calibration",
            has_route,
            "路线矩阵已确认",
            "生成 route_matrix_confirm.json。",
        ),
        stage_check(
            "stage_6_voc",
            has_voc,
            "评论 VOC 证据已生成",
            "等待评论分析完成，生成 voc_evidence_packet.json。",
        ),
        stage_check(
            "stage_7_analysis",
            stage_7_done,
            stage_7_evidence,
            "运行 build_analysis_report.py 或 AI 手写报告。",
        ),
    ]


def stage_check(stage: str, passed: bool, ok_note: str, next_step: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "completed" if passed else "pending",
        "evidence": ok_note if passed else "",
        "next_step": "" if passed else next_step,
    }


def infer_current_stage(stage_checks: list[dict[str, Any]]) -> dict[str, Any]:
    for check in stage_checks:
        if check["status"] != "completed":
            return {
                "stage": check["stage"],
                "status": check["status"],
                "label": stage_label(check["stage"]),
                "next_step": check["next_step"],
            }
    return {
        "stage": "completed",
        "status": "completed",
        "label": "全部阶段完成",
        "next_step": "报告已交付，可归档。",
    }


def stage_label(stage: str) -> str:
    return {
        "stage_1_inputs": "Stage 1 数据输入",
        "stage_4_candidate_pool": "Stage 4 候选品池",
        "stage_5_route_calibration": "Stage 5 路线确认",
        "stage_6_voc": "Stage 6 评论 VOC",
        "stage_7_analysis": "Stage 7 分析报告",
        "completed": "全部完成",
    }.get(stage, stage or "未知阶段")


def build_blockers(
    source_quality: dict[str, Any],
    stage_checks: list[dict[str, Any]],
    qa_result: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if source_quality.get("level") == "blocked":
        blockers.append({
            "type": "data_quality",
            "severity": "blocking",
            "item": "数据源缺失",
            "impact": "无法进行多源交叉分析。",
            "next_step": source_quality.get("next_step", ""),
            "source": "inputs/ 目录",
        })
    for check in stage_checks:
        if check["status"] != "completed":
            blockers.append({
                "type": "stage_pending",
                "severity": "blocking" if check["stage"] in {"stage_1_inputs", "stage_7_analysis"} else "warning",
                "item": stage_label(check["stage"]),
                "impact": "该阶段未完成，后续阶段无法推进。",
                "next_step": check["next_step"],
                "source": check["stage"],
            })
    qa_exists = artifacts.get("delivery_qa", {}).get("exists", False)
    # 检查 stage 7 是否已有产出（report/html/xlsx）
    stage_7_has_artifacts = (
        artifacts.get("analysis_report_data", {}).get("exists", False)
        and artifacts.get("analysis_html", {}).get("exists", False)
        and artifacts.get("analysis_xlsx", {}).get("exists", False)
    )
    if qa_exists and qa_result:
        qa_version = qa_result.get("qa_rule_version", "")
        if not qa_version:
            blockers.append({
                "type": "qa_stale",
                "severity": "blocking",
                "item": "QA 结果缺少规则版本号（旧格式，可能遗漏值一致性校验等检查项）",
                "impact": "旧 QA 文件不包含新增检查项（值一致性、禁止模式等），应重跑 QA。",
                "next_step": "运行 build_analysis_report.py 重新生成 QA 结果。",
                "source": "analysis/delivery_qa_result.json",
            })
        elif qa_version != _current_qa_version():
            blockers.append({
                "type": "qa_stale",
                "severity": "blocking",
                "item": f"QA 规则版本过期 (当前: {_current_qa_version()}, 文件: {qa_version})",
                "impact": "旧规则可能遗漏新增检查项（如值一致性校验、禁止模式等），需按当前规则重新 QA。",
                "next_step": "运行 build_analysis_report.py 重新生成 QA 结果。",
                "source": "analysis/delivery_qa_result.json",
            })
        elif qa_result.get("status") != "pass":
            blockers.append({
                "type": "qa_failure",
                "severity": "blocking",
                "item": f"QA 校验未通过: {qa_result.get('failures', [])}",
                "impact": "报告存在质量问题，需修复后重新 QA。",
                "next_step": "查看 delivery_qa_result.json 中的失败项并修复。",
                "source": "analysis/delivery_qa_result.json",
            })
    elif stage_7_has_artifacts and not qa_exists:
        # 产出已生成但 QA 文件缺失 → 阻断
        blockers.append({
            "type": "qa_missing",
            "severity": "blocking",
            "item": "Stage 7 产出已存在但 QA 文件缺失（delivery_qa_result.json）",
            "impact": "报告质量未经校验，无法确认是否满足交付标准。",
            "next_step": "运行 build_analysis_report.py 完成 QA 校验。",
            "source": "analysis/delivery_qa_result.json",
        })
    return blockers[:20]


def _current_qa_version() -> str:
    from packages.research_core.pipeline.constants import QA_RULE_VERSION
    return QA_RULE_VERSION


def build_next_actions(
    blockers: list[dict[str, Any]],
    stage_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for blocker in blockers:
        actions.append({
            "label": blocker.get("item", ""),
            "reason": blocker.get("impact", ""),
            "action_type": "unblock",
            "source": "audit.blockers",
            "next_step": blocker.get("next_step", ""),
        })
    if not actions:
        pending = next((c for c in stage_checks if c["status"] != "completed"), None)
        if pending:
            actions.append({
                "label": stage_label(str(pending.get("stage", ""))),
                "reason": "继续完成当前未完成阶段。",
                "action_type": "continue_stage",
                "source": "audit.stage_checks",
                "next_step": pending.get("next_step", ""),
            })
    return actions[:10]


def build_summary(
    current_stage: dict[str, Any],
    blockers: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
) -> str:
    blocker_text = f"阻塞 {len(blockers)} 项" if blockers else "暂无硬阻塞"
    next_action = (
        next_actions[0].get("next_step") or next_actions[0].get("reason")
        if next_actions
        else "按当前阶段继续推进。"
    )
    return f"{current_stage.get('label')} / {current_stage.get('status')}；{blocker_text}；下一步：{next_action}"
