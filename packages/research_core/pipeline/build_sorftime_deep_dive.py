#!/usr/bin/env python3
"""Build P4 Sorftime search-demand deep-dive artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from packages.research_core.contracts import (
    P4ContractError,
    P4_SCHEMA_VERSION,
    P4_STAGE_ID,
    validate_deep_snapshot,
    validate_p4_evidence_packet,
    validate_p4_preconditions,
)
from packages.research_core.contracts.p0_contracts import P0_SCHEMA_VERSION
from packages.research_core.pipeline._utils import as_list, first_text, load_json, numeric_value, _now_iso, _write_json, _unique_texts
from packages.research_core.pipeline.quick_market_check import validate_progress


SNAPSHOT_DIR = "mcp_snapshots"
SEARCH_DEMAND_DIR = "search_demand"
SORFTIME_SNAPSHOT_NAME = "sorftime_deep_snapshot.json"
SEARCH_DEMAND_PACKET_NAME = "search_demand_evidence_packet.json"
SORFTIME_SOURCE_NAME = "sorftime"

P4_SORFTIME_INPUT_ARTIFACTS = [
    "candidate_pool.json",
    "route_matrix_confirm.json",
    "data_completeness_check.json",
    "progress.json",
]
P4_SORFTIME_OUTPUT_ARTIFACTS = [
    f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}",
    f"{SEARCH_DEMAND_DIR}/{SEARCH_DEMAND_PACKET_NAME}",
]

EVIDENCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "item_type": "category_search",
        "tools": ("category_search_from_product_name", "search_categories_broadly"),
        "metric_unit": "category_node",
        "aggregation_unit": "category",
        "sample_scope": "category_candidate",
        "expected_fields": ("nodeid", "类目名称", "Top100产品月销量", "Top100产品月销额", "平均星级", "平均评价数量", "平均价格", "销量前3的产品月销量占比", "销量前3的品牌月销量占比", "销量前3的卖家月销量占比", "上线3个月内的新品销量占比", "中国卖家占比", "亚马逊自营月销量占比"),
    },
    {
        "item_type": "category_top100",
        "tools": ("category_report", "category_report_from_history"),
        "metric_unit": "mixed",
        "aggregation_unit": "category",
        "sample_scope": "category_top100",
        "expected_fields": ("Top100产品.ASIN", "Top100产品.价格", "Top100产品.月销量", "Top100产品.月销额", "Top100产品.评论数", "Top100产品.星级", "Top100产品.卖家", "类目统计报告.nodeid", "类目统计报告.top100产品月销量", "类目统计报告.top100产品月销额", "类目统计报告.top3_product_sales_volume_share", "类目统计报告.top3_brands_sales_volume_share", "类目统计报告.top3_seller_sales_volume_share", "类目统计报告.amazonOwned_sales_volume_share", "类目统计报告.average_price", "类目统计报告.median_price"),
    },
    {
        "item_type": "category_trend",
        "tools": ("category_trend", "category_report_from_history"),
        "metric_unit": "series",
        "aggregation_unit": "category",
        "sample_scope": "category_trend",
        "expected_fields": ("类目月销量趋势", "series_sample", "trend_points"),
    },
    {
        "item_type": "keyword_detail",
        "tools": ("keyword_detail",),
        "metric_unit": "keyword",
        "aggregation_unit": "keyword",
        "sample_scope": "keyword_demand",
        "expected_fields": ("关键词", "周搜索量", "周搜索排名", "月搜索量", "推荐cpc竞价", "词搜索量旺季", "搜索结果竞品数量"),
    },
    {
        "item_type": "keyword_trend",
        "tools": ("keyword_trend",),
        "metric_unit": "series",
        "aggregation_unit": "keyword",
        "sample_scope": "keyword_trend",
        "expected_fields": ("搜索量趋势", "搜索量趋势_sample", "搜索排名趋势", "推荐竞价趋势"),
    },
    {
        "item_type": "keyword_expansion",
        "tools": ("keyword_extends",),
        "metric_unit": "keyword",
        "aggregation_unit": "keyword",
        "sample_scope": "keyword_expansion",
        "expected_fields": ("关键词", "周搜索量", "周搜索排名", "月搜索量", "cpc推荐竞价", "季节性"),
    },
    {
        "item_type": "keyword_search_results",
        "tools": ("keyword_search_results",),
        "metric_unit": "mixed",
        "aggregation_unit": "serp",
        "sample_scope": "serp_result",
        "expected_fields": ("ASIN", "标题", "价格", "月销量", "品牌", "卖家", "排名", "月搜索量", "自然位"),
    },
    {
        "item_type": "asin_traffic_terms",
        "tools": ("product_traffic_terms",),
        "metric_unit": "keyword",
        "aggregation_unit": "asin",
        "sample_scope": "asin_traffic",
        "expected_fields": ("关键词", "ASIN", "自然位", "广告位", "曝光时间", "搜索量"),
    },
    {
        "item_type": "competitor_keywords",
        "tools": ("competitor_product_keywords",),
        "metric_unit": "keyword",
        "aggregation_unit": "asin",
        "sample_scope": "competitor_keyword",
        "expected_fields": ("关键词", "ASIN", "自然位", "搜索量", "销量"),
    },
    {
        "item_type": "hot_product_features",
        "tools": ("similar_product_feature", "potential_product"),
        "metric_unit": "feature",
        "aggregation_unit": "product",
        "sample_scope": "hot_feature",
        "expected_fields": ("特征", "占比", "热销特征", "产品", "ASIN"),
    },
    {
        "item_type": "product_detail",
        "tools": ("product_detail",),
        "metric_unit": "mixed",
        "aggregation_unit": "asin",
        "sample_scope": "representative_asin",
        "expected_fields": ("asin", "price", "monthly_sales", "monthly_revenue", "rating", "ratings", "seller", "brand", "category", "nodeId"),
    },
    {
        "item_type": "product_reviews",
        "tools": ("product_reviews",),
        "metric_unit": "review",
        "aggregation_unit": "asin",
        "sample_scope": "light_voc_readiness",
        "expected_fields": ("review", "rating", "title", "date", "content", "asin"),
    },
)


class P4SorftimeError(ValueError):
    """Raised when P4-3 Sorftime artifacts cannot be built."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build P4 Sorftime search-demand deep-dive artifacts.")
    parser.add_argument("run_dir", type=Path, help="Path to runs/<run_id> directory")
    parser.add_argument(
        "--snapshot-source",
        type=Path,
        help="Optional P4 deep snapshot or Sorftime probe raw JSON to reuse.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_sorftime_deep_dive(args.run_dir, snapshot_source=args.snapshot_source)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_sorftime_deep_dive(
    run_dir: Path | str,
    *,
    snapshot_source: Path | str | None = None,
) -> dict[str, Path]:
    run_path = Path(run_dir).expanduser().resolve()
    if not run_path.exists():
        raise P4SorftimeError(f"run_dir not found: {run_path}")

    progress_path = run_path / "progress.json"
    try:
        validate_p4_preconditions(run_path)
        workflow_state = load_json(run_path / "workflow_state.json")
        route_matrix = load_json(run_path / "route_matrix_confirm.json")
        candidate_pool = load_json(run_path / "candidate_pool.json")
        progress = load_json(progress_path)

        snapshot_path = ensure_sorftime_deep_snapshot(
            run_path,
            workflow_state,
            route_matrix,
            candidate_pool,
            snapshot_source=Path(snapshot_source).expanduser().resolve() if snapshot_source else None,
        )
        snapshot = load_json(snapshot_path)
        validate_deep_snapshot(snapshot, expected_source_name=SORFTIME_SOURCE_NAME)

        evidence_packet = build_search_demand_evidence_packet(
            snapshot,
            workflow_state,
            route_matrix,
            candidate_pool,
            run_path,
        )
        validate_p4_evidence_packet(evidence_packet, expected_primary_source=SORFTIME_SOURCE_NAME)

        packet_path = run_path / SEARCH_DEMAND_DIR / SEARCH_DEMAND_PACKET_NAME
        _write_json(packet_path, evidence_packet)

        progress = build_sorftime_success_progress(progress, workflow_state, evidence_packet)
        validate_progress(progress)
        _write_json(progress_path, progress)

        return {
            "sorftime_deep_snapshot": snapshot_path,
            "search_demand_evidence_packet": packet_path,
            "progress": progress_path,
        }
    except Exception as exc:
        _write_failure_progress(run_path, progress_path, str(exc))
        raise P4SorftimeError(str(exc)) from exc


def ensure_sorftime_deep_snapshot(
    run_path: Path,
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    *,
    snapshot_source: Path | None = None,
) -> Path:
    target = run_path / SNAPSHOT_DIR / SORFTIME_SNAPSHOT_NAME
    if target.exists():
        snapshot = load_json(target)
        validate_deep_snapshot(snapshot, expected_source_name=SORFTIME_SOURCE_NAME)
        return target
    if snapshot_source is None:
        raise P4SorftimeError(f"missing Sorftime deep snapshot: {target}")
    if not snapshot_source.exists():
        raise P4SorftimeError(f"snapshot source not found: {snapshot_source}")

    source = load_json(snapshot_source)
    if _looks_like_p4_snapshot(source):
        snapshot = deepcopy(source)
        snapshot["run_id"] = _run_id(workflow_state, run_path)
        _ensure_route_lineage(snapshot, route_matrix)
        validate_deep_snapshot(snapshot, expected_source_name=SORFTIME_SOURCE_NAME)
    else:
        snapshot = normalize_sorftime_probe_snapshot(source, workflow_state, route_matrix, candidate_pool, run_path)
        validate_deep_snapshot(snapshot, expected_source_name=SORFTIME_SOURCE_NAME)

    _write_json(target, snapshot)
    return target


def normalize_sorftime_probe_snapshot(
    probe: dict[str, Any],
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    now = _now_iso()
    route_refs, selected_routes = _route_lineage(route_matrix)
    probe_inputs = probe.get("probe_inputs") if isinstance(probe.get("probe_inputs"), dict) else {}
    tool_records = [item for item in as_list(probe.get("tool_calls")) if isinstance(item, dict)]
    if not tool_records:
        raise P4SorftimeError("Sorftime probe snapshot must include tool_calls")

    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    data_gaps: list[dict[str, Any]] = []
    for index, record in enumerate(tool_records):
        base_tool_name = _base_tool_name(record.get("tool_name"))
        status = _normalize_tool_status(record.get("status"))
        call_id = f"sorftime-deep-call-{index + 1}"
        params = record.get("request") if isinstance(record.get("request"), dict) else {}
        tool_calls.append(
            {
                "call_id": call_id,
                "tool_name": base_tool_name,
                "params": params,
                "status": status,
                "started_at": first_text(record.get("tested_at"), probe.get("created_at"), now),
                "finished_at": first_text(record.get("tested_at"), probe.get("created_at"), now),
                "source_probe_tool_name": record.get("tool_name", ""),
            }
        )
        raw_result = _probe_raw_result(record)
        result: dict[str, Any] = {
            "result_id": f"sorftime-deep-result-{index + 1}",
            "call_id": call_id,
            "tool_name": base_tool_name,
            "status": status,
        }
        if raw_result is not None:
            result["raw_result"] = raw_result
        else:
            result["normalized_preview"] = {
                "available_fields": record.get("available_fields") or [],
                "field_notes": record.get("field_notes") or [],
            }
        tool_results.append(result)

        if status == "error":
            error = record.get("error") if isinstance(record.get("error"), dict) else {}
            errors.append(
                {
                    "type": first_text(error.get("type"), "tool_error"),
                    "tool_name": base_tool_name,
                    "message": first_text(error.get("message"), "Sorftime tool call failed."),
                    "params_summary": params,
                }
            )
            data_gaps.append(
                {
                    "type": "tool_call_failed",
                    "tool_name": base_tool_name,
                    "evidence_type": first_text(record.get("evidence_type"), base_tool_name),
                    "severity": "warning",
                }
            )
        for field in as_list(record.get("missing_or_unstable_fields")):
            if first_text(field):
                data_gaps.append(
                    {
                        "type": "missing_or_unstable_field",
                        "tool_name": base_tool_name,
                        "field": first_text(field),
                        "severity": "warning",
                    }
                )

    return {
        "schema_version": P4_SCHEMA_VERSION,
        "snapshot_id": f"{_run_id(workflow_state, run_path)}-sorftime-deep",
        "run_id": _run_id(workflow_state, run_path),
        "source_name": SORFTIME_SOURCE_NAME,
        "source_doc_refs": [
            "docs/sorftime-mcp-工具调用策略.md#stage-7-深扫",
            "docs/references/p4_mcp_capability_mapping.md#sorftime",
        ],
        "route_refs": route_refs,
        "selected_routes": selected_routes,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "errors": errors,
        "data_gaps": _dedupe_dicts(data_gaps),
        "created_at": first_text(probe.get("created_at"), now),
        "retry_policy": {
            "max_attempts": 1,
            "reuse_existing_snapshot": True,
            "allow_network_call": False,
        },
        "force_refresh": False,
        "input_lineage": {
            "workflow_ref": _run_id(workflow_state, run_path),
            "route_refs": route_refs,
            "selected_routes": selected_routes,
            "source_candidate_pool": "candidate_pool.json",
            "site": first_text(workflow_state.get("site"), probe_inputs.get("site"), "US"),
            "amzSite": first_text(probe_inputs.get("amzSite"), probe_inputs.get("site"), workflow_state.get("site"), "US"),
            "seed_keyword": first_text(probe_inputs.get("keyword"), probe_inputs.get("productName"), ""),
            "nodeId": first_text(probe_inputs.get("nodeId"), probe_inputs.get("nodeid"), probe_inputs.get("node_id")),
            "nodeIdPath": first_text(probe_inputs.get("nodeIdPath"), probe_inputs.get("node_id_path")),
            "candidate_pool_ref": candidate_pool.get("workflow_ref", ""),
        },
    }


def build_search_demand_evidence_packet(
    snapshot: dict[str, Any],
    workflow_state: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
    run_path: Path,
) -> dict[str, Any]:
    route_refs, selected_routes = _route_lineage(route_matrix)
    call_index_by_id = {
        str(call.get("call_id")): index
        for index, call in enumerate(snapshot.get("tool_calls") or [])
        if isinstance(call, dict)
    }
    results = [item for item in as_list(snapshot.get("tool_results")) if isinstance(item, dict)]
    data_gaps = list(as_list(snapshot.get("data_gaps")))
    errors = list(as_list(snapshot.get("errors")))
    evidence_items: list[dict[str, Any]] = []
    metric_basis: dict[str, dict[str, Any]] = {}
    derived_metrics: dict[str, dict[str, Any]] = {}

    for spec in EVIDENCE_SPECS:
        result_index, result = _find_result(results, spec["tools"])
        result_ref = f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}#tool_results[{result_index}]" if result_index >= 0 else f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}#tool_results[0]"
        call_ref = _call_ref(result, call_index_by_id)
        basis_id = f"sorftime_{spec['item_type']}_basis"
        tool_name = _base_tool_name(result.get("tool_name") if isinstance(result, dict) else first_text(spec["tools"][0]))
        rows = _extract_rows(_result_payload(result))
        normalized = _normalize_evidence_value(rows, spec["expected_fields"])
        item_gaps = _field_gaps(spec, result, rows, normalized, result_ref)
        data_gaps.extend(item_gaps)
        lineage = _extract_lineage(result, rows, snapshot, route_matrix, candidate_pool)

        metric_basis[basis_id] = _metric_basis(
            source_name=SORFTIME_SOURCE_NAME,
            tool_name=tool_name,
            metric_unit=spec["metric_unit"],
            aggregation_unit=spec["aggregation_unit"],
            sample_scope=spec["sample_scope"],
            workflow_state=workflow_state,
            snapshot=snapshot,
            result=result,
            route_refs=route_refs,
            selected_routes=selected_routes,
            lineage=lineage,
        )
        evidence_items.append(
            {
                "item_id": f"sorftime_{spec['item_type']}",
                "item_type": spec["item_type"],
                "facts": {
                    "tool_name": tool_name,
                    "raw_value": _result_payload(result),
                    "normalized_value": normalized,
                    "node_mapping_input": lineage,
                    "expected_fields": list(spec["expected_fields"]),
                    "source_status": result.get("status", "missing") if isinstance(result, dict) else "missing",
                },
                "metric_basis_ref": basis_id,
                "evidence_refs": [result_ref],
                "source_refs": [call_ref],
            }
        )
        derived_metrics[f"{spec['item_type']}_signal"] = {
            "value": _first_metric_value(normalized),
            "raw_value": _result_payload(result),
            "normalized_value": normalized,
            "metric_basis_ref": basis_id,
            "evidence_refs": [result_ref],
        }

    if errors:
        data_gaps.extend(_error_gaps(errors))

    packet = {
        "schema_version": P4_SCHEMA_VERSION,
        "packet_id": "search_demand_evidence_packet",
        "run_id": _run_id(workflow_state, run_path),
        "primary_source": SORFTIME_SOURCE_NAME,
        "cross_check_sources": ["sellersprite"],
        "source_snapshot_refs": [f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}#snapshot"],
        "route_refs": route_refs,
        "selected_routes": selected_routes,
        "evidence_items": evidence_items,
        "derived_metrics": derived_metrics,
        "metric_basis": metric_basis,
        "data_gaps": _dedupe_dicts(data_gaps),
        "blocking_gaps": [],
        "confidence": _packet_confidence(data_gaps),
        "source_refs": _unique_texts(
            [f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}#snapshot"]
            + [ref for item in evidence_items for ref in item.get("evidence_refs", [])]
        ),
        "created_at": _now_iso(),
        "generation_provenance": {
            "execution_mode": "script_generated",
            "source_stage": "p4_sorftime_search_demand",
            "source_snapshot_path": f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}",
            "source_candidate_pool": "candidate_pool.json",
            "route_matrix_ref": "route_matrix_confirm.json",
            "does_not_complete_stage_6": True,
        },
    }
    return packet


def build_sorftime_success_progress(
    progress: dict[str, Any],
    workflow_state: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    now = _now_iso()
    progress = _progress_template(progress, workflow_state)
    completed = list(progress.get("completed_artifacts") or [])
    for artifact in P4_SORFTIME_OUTPUT_ARTIFACTS:
        if artifact not in completed:
            completed.append(artifact)

    stages = deepcopy(progress.get("stages") or {})
    previous_stage = stages.get(P4_STAGE_ID) if isinstance(stages.get(P4_STAGE_ID), dict) else {}
    stages[P4_STAGE_ID] = {
        "status": "running",
        "attempts": int(previous_stage.get("attempts", 0) or 0) + 1,
        "input_artifacts": P4_SORFTIME_INPUT_ARTIFACTS,
        "output_artifacts": P4_SORFTIME_OUTPUT_ARTIFACTS,
        "validation_checks": [
            {"name": "p4_preconditions", "pass": True, "detail": "P3 route matrix is confirmed."},
            {"name": "sorftime_deep_snapshot_schema", "pass": True, "detail": "Snapshot passed P4 deep snapshot contract."},
            {"name": "search_demand_evidence_schema", "pass": True, "detail": f"confidence={evidence_packet.get('confidence')}"},
            {"name": "p4_scope_no_downstream_artifacts", "pass": True, "detail": "P4-3 only builds Sorftime search-demand artifacts."},
        ],
        "last_error": "",
        "next_required_user_action": "",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }

    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P4_STAGE_ID,
            "updated_at": now,
            "global_blockers": [],
            "next_action": {
                "type": "run_stage",
                "stage_id": P4_STAGE_ID,
                "description": "Sorftime search demand evidence is ready; proceed to P4-4 data normalization and conflict review.",
                "next_substage": "P4-4",
            },
            "completed_artifacts": completed,
            "stages": stages,
            "workflow_ref": progress.get("workflow_ref") or workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
        }
    )
    return progress


def _write_failure_progress(run_path: Path, progress_path: Path, error: str) -> None:
    now = _now_iso()
    workflow_state = load_json(run_path / "workflow_state.json", required=False)
    progress = _progress_template(load_json(progress_path, required=False), workflow_state)
    status = _failure_status(error)
    stages = deepcopy(progress.get("stages") or {})
    previous_stage = stages.get(P4_STAGE_ID) if isinstance(stages.get(P4_STAGE_ID), dict) else {}
    stages[P4_STAGE_ID] = {
        "status": status,
        "attempts": int(previous_stage.get("attempts", 0) or 0) + 1,
        "input_artifacts": P4_SORFTIME_INPUT_ARTIFACTS,
        "output_artifacts": P4_SORFTIME_OUTPUT_ARTIFACTS,
        "validation_checks": [{"name": "p4_sorftime_deep_dive", "pass": False, "detail": error}],
        "last_error": error,
        "next_required_user_action": "Fix P4-3 inputs or rerun P3 confirmation before Sorftime deep dive.",
        "resume_policy": {
            "reuse_existing_artifacts": True,
            "allow_repeat_mcp_call": False,
            "force_refresh": False,
        },
    }
    progress.update(
        {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P4_STAGE_ID,
            "updated_at": now,
            "global_blockers": [{"stage_id": P4_STAGE_ID, "error": error}],
            "next_action": {
                "type": "fix_stage_error" if status == "failed" else "blocked",
                "stage_id": P4_STAGE_ID,
                "description": "Resolve P4-3 preconditions or Sorftime snapshot schema before rerunning Sorftime deep dive.",
            },
            "stages": stages,
        }
    )
    try:
        validate_progress(progress)
        _write_json(progress_path, progress)
    except Exception:
        pass


def _progress_template(progress: dict[str, Any], workflow_state: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    if not isinstance(progress, dict) or not progress:
        return {
            "schema_version": P0_SCHEMA_VERSION,
            "current_stage": P4_STAGE_ID,
            "updated_at": now,
            "global_blockers": [],
            "next_action": {
                "type": "run_stage",
                "stage_id": P4_STAGE_ID,
                "description": "Run P4 Sorftime search-demand deep dive.",
            },
            "completed_artifacts": [],
            "stages": {},
            "workflow_ref": workflow_state.get("workflow_id") or workflow_state.get("run_id") or "",
        }
    progress.setdefault("schema_version", P0_SCHEMA_VERSION)
    progress.setdefault("current_stage", P4_STAGE_ID)
    progress.setdefault("updated_at", now)
    progress.setdefault("global_blockers", [])
    progress.setdefault("next_action", {})
    progress.setdefault("completed_artifacts", [])
    progress.setdefault("stages", {})
    progress["workflow_ref"] = progress.get("workflow_ref") or workflow_state.get("workflow_id") or workflow_state.get("run_id") or ""
    return progress


def _looks_like_p4_snapshot(data: dict[str, Any]) -> bool:
    return data.get("schema_version") == P4_SCHEMA_VERSION and data.get("source_name") == SORFTIME_SOURCE_NAME


def _ensure_route_lineage(snapshot: dict[str, Any], route_matrix: dict[str, Any]) -> None:
    route_refs, selected_routes = _route_lineage(route_matrix)
    snapshot["route_refs"] = route_refs
    snapshot["selected_routes"] = selected_routes
    lineage = snapshot.get("input_lineage") if isinstance(snapshot.get("input_lineage"), dict) else {}
    lineage.update({"route_refs": route_refs, "selected_routes": selected_routes})
    snapshot["input_lineage"] = lineage


def _route_lineage(route_matrix: dict[str, Any]) -> tuple[list[str], list[str]]:
    selected = [item for item in as_list(route_matrix.get("selected_routes")) if isinstance(item, dict)]
    route_refs = [f"route_matrix_confirm.json#selected_routes[{index}]" for index, _ in enumerate(selected)]
    selected_routes = [
        first_text(route.get("route_id"), route.get("candidate_id"), route.get("route_name"), route.get("label"), f"route_{index + 1}")
        for index, route in enumerate(selected)
    ]
    if not route_refs:
        raise P4SorftimeError("route_matrix_confirm.selected_routes must not be empty")
    return route_refs, selected_routes


def _find_result(results: list[dict[str, Any]], tool_names: tuple[str, ...]) -> tuple[int, dict[str, Any]]:
    for index, result in enumerate(results):
        base_name = _base_tool_name(result.get("tool_name"))
        if base_name in tool_names:
            return index, result
    for index, result in enumerate(results):
        base_name = _base_tool_name(result.get("tool_name"))
        if any(name in base_name or base_name in name for name in tool_names):
            return index, result
    if results:
        return 0, results[0]
    raise P4SorftimeError("sorftime deep snapshot must include tool_results")


def _call_ref(result: dict[str, Any], call_index_by_id: dict[str, int]) -> str:
    call_id = str(result.get("call_id") or "")
    index = call_index_by_id.get(call_id, 0)
    return f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}#tool_calls[{index}]"


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


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            rows.extend(_extract_rows(item))
        return rows
    if not isinstance(payload, dict):
        return rows
    for key in ("items", "rows", "items_sample", "rows_sample", "Top100产品_sample", "类目统计报告_sample", "top5_product_sample", "ASINs_sample"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend([item for item in value if isinstance(item, dict)])
        elif isinstance(value, dict):
            rows.append(value)
    data = payload.get("data")
    if isinstance(data, list):
        rows.extend([item for item in data if isinstance(item, dict)])
    elif isinstance(data, dict):
        rows.append(data)
    if not rows and payload:
        rows.append(payload)
    return rows


def _normalize_evidence_value(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in fields:
        value = _first_field(rows, field)
        if value not in (None, "", []):
            values[field] = value
    numeric_values = {key: number for key, value in values.items() if (number := _localized_numeric_value(value)) is not None}
    return {
        "field_values": values,
        "numeric_values": numeric_values,
        "sample_count": len(rows),
    }


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


def _error_gaps(errors: list[Any]) -> list[dict[str, Any]]:
    gaps = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        gaps.append(
            {
                "type": "snapshot_error",
                "tool_name": first_text(error.get("tool_name"), "unknown"),
                "message": first_text(error.get("message"), error.get("type"), "Sorftime snapshot error."),
                "severity": "warning",
            }
        )
    return gaps


def _metric_basis(
    *,
    source_name: str,
    tool_name: str,
    metric_unit: str,
    aggregation_unit: str,
    sample_scope: str,
    workflow_state: dict[str, Any],
    snapshot: dict[str, Any],
    result: dict[str, Any],
    route_refs: list[str],
    selected_routes: list[str],
    lineage: dict[str, Any],
) -> dict[str, Any]:
    params = _call_params_for_result(snapshot, result)
    site = first_text(params.get("amzSite"), params.get("keywordSupportSite"), workflow_state.get("site"), snapshot.get("input_lineage", {}).get("site"), "US")
    data_window = first_text(params.get("month"), params.get("startDate"), params.get("endDate"), snapshot.get("data_window"), "30d")
    return {
        "source_name": source_name,
        "tool_name": tool_name,
        "site": site,
        "marketplace": site,
        "currency": first_text(snapshot.get("currency"), workflow_state.get("currency"), "USD"),
        "time_window": data_window,
        "data_window": data_window,
        "sample_scope": sample_scope,
        "metric_unit": metric_unit,
        "aggregation_unit": aggregation_unit,
        "parent_child_basis": first_text(params.get("parent_child_basis"), lineage.get("parent_child_basis"), "unknown"),
        "collection_method": "sorftime_deep_snapshot",
        "collected_at": first_text(snapshot.get("created_at"), _now_iso()),
        "input_lineage": {
            "route_refs": route_refs,
            "selected_routes": selected_routes,
            "params": params,
            "nodeId": lineage.get("nodeId", ""),
            "nodeIdPath": lineage.get("nodeIdPath", ""),
            "source_snapshot": f"{SNAPSHOT_DIR}/{SORFTIME_SNAPSHOT_NAME}",
        },
    }


def _call_params_for_result(snapshot: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    call_id = result.get("call_id") if isinstance(result, dict) else ""
    for call in as_list(snapshot.get("tool_calls")):
        if isinstance(call, dict) and call.get("call_id") == call_id and isinstance(call.get("params"), dict):
            return call["params"]
    return {}


def _extract_lineage(
    result: dict[str, Any],
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
    route_matrix: dict[str, Any],
    candidate_pool: dict[str, Any],
) -> dict[str, Any]:
    params = _call_params_for_result(snapshot, result)
    lineage = snapshot.get("input_lineage") if isinstance(snapshot.get("input_lineage"), dict) else {}
    node_path = first_text(
        params.get("nodeIdPath"),
        params.get("node_id_path"),
        _first_field(rows, "nodeIdPath"),
        _first_field(rows, "nodeid"),
        lineage.get("nodeIdPath"),
        _nested_first(route_matrix, ("confirmed_boundary", "nodeIdPath")),
        _nested_first(candidate_pool, ("summary", "nodeIdPath")),
    )
    node_id = first_text(params.get("nodeId"), params.get("nodeid"), _first_field(rows, "nodeid"), lineage.get("nodeId"))
    keyword = first_text(params.get("keyword"), params.get("productName"), _first_field(rows, "关键词"), _first_field(rows, "keyword"), lineage.get("seed_keyword"))
    return {
        "nodeId": node_id,
        "nodeIdPath": node_path,
        "keyword": keyword,
        "node_mapping_status": "pending_cross_check" if node_path or node_id else "missing",
        "parent_child_basis": first_text(params.get("parent_child_basis"), "unknown"),
    }


def _first_field(rows: list[dict[str, Any]], field: str) -> Any:
    for row in rows:
        value = _case_insensitive_get(row, field)
        if value not in (None, "", []):
            return value
    return None


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


def _first_metric_value(normalized: dict[str, Any]) -> Any:
    numeric_values = normalized.get("numeric_values") if isinstance(normalized, dict) else {}
    if isinstance(numeric_values, dict) and numeric_values:
        return next(iter(numeric_values.values()))
    field_values = normalized.get("field_values") if isinstance(normalized, dict) else {}
    if isinstance(field_values, dict) and field_values:
        return next(iter(field_values.values()))
    return None


def _localized_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for pattern in (r"([-+]?\d[\d,]*\.?\d*)%", r"([-+]?\d[\d,]*\.?\d*)"):
            match = re.search(pattern, text)
            if match:
                number = match.group(1).replace(",", "")
                try:
                    parsed = float(number)
                except ValueError:
                    continue
                return parsed / 100 if "%" in match.group(0) else parsed
    return None


def _packet_confidence(data_gaps: list[Any]) -> str:
    severe_count = sum(1 for gap in data_gaps if isinstance(gap, dict) and gap.get("type") in {"tool_result_unavailable", "tool_call_failed"})
    if severe_count >= 2:
        return "low"
    if data_gaps:
        return "medium"
    return "high"


def _failure_status(error: str) -> str:
    text = error.lower()
    if "decision must be confirm" in text or "overall_level must not be blocker" in text or "stage_5_route_matrix.status must be done" in text:
        return "blocked"
    return "failed"


def _run_id(workflow_state: dict[str, Any], run_path: Path) -> str:
    return first_text(workflow_state.get("workflow_id"), workflow_state.get("run_id"), run_path.name)


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




