"""Build a machine-readable route confirmation packet for Stage 7."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_NAME = "route_matrix_confirm.json"


def build_route_matrix_confirm(run_dir: Path | str) -> dict[str, Any]:
    run_path = Path(run_dir).expanduser().resolve()
    workflow_state = load_json(run_path / "workflow_state.json")
    review_batch = load_json(run_path / "review_asin_batch.json")
    market = load_json(run_path / "market_structure" / "market_structure_evidence_packet.json")
    search = load_json(run_path / "search_demand" / "search_demand_evidence_packet.json")

    route_rows = as_list(market.get("route_market_fit"))
    if not route_rows:
        route_rows = infer_route_rows_from_review_batch(review_batch)
    route_matrix = [normalize_route_row(row, review_batch, search) for row in route_rows]

    boundary = first_dict(review_batch.get("confirmed_boundary"), ((workflow_state.get("known_inputs") or {}).get("confirmed_boundary")))
    selected_route = first_text(
        review_batch.get("candidate_name"),
        boundary.get("mainline") if isinstance(boundary, dict) else "",
        (workflow_state.get("known_inputs") or {}).get("confirmed_boundary"),
        (workflow_state.get("known_inputs") or {}).get("confirmed_stage0_route"),
    )

    return {
        "packet_id": "route_matrix_confirm",
        "packet_version": "stage5-route-matrix-confirm-v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workflow_id": workflow_state.get("workflow_id") or review_batch.get("workflow_id") or run_path.name,
        "site": workflow_state.get("site") or review_batch.get("site") or "US",
        "selected_route": selected_route,
        "recommended_mainline": selected_route,
        "confirmed_boundary": boundary,
        "route_matrix": route_matrix,
        "category_selection_derivation": build_category_selection_derivation(
            workflow_state,
            review_batch,
            market,
            search,
            selected_route,
        ),
        "source_refs": [
            path_ref(run_path / "workflow_state.json"),
            path_ref(run_path / "review_asin_batch.json"),
            path_ref(run_path / "market_structure" / "market_structure_evidence_packet.json"),
            path_ref(run_path / "search_demand" / "search_demand_evidence_packet.json"),
        ],
        "data_boundary": "路线确认包由既有 run 证据生成；如运营后续调整路线角色，应重新生成或手动更新本文件。",
    }


def write_route_matrix_confirm(run_dir: Path | str) -> Path:
    run_path = Path(run_dir).expanduser().resolve()
    packet = build_route_matrix_confirm(run_path)
    output_path = run_path / DEFAULT_OUTPUT_NAME
    output_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def infer_route_rows_from_review_batch(review_batch: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_route: dict[str, dict[str, Any]] = {}
    counts = Counter(item.get("route") for item in as_list(review_batch.get("asin_batch")) if isinstance(item, dict))
    for item in as_list(review_batch.get("asin_batch")):
        if not isinstance(item, dict):
            continue
        route_id = str(item.get("route") or "unclassified")
        row = rows_by_route.setdefault(
            route_id,
            {
                "route_id": route_id,
                "route_name": route_id,
                "role_from_route_matrix": "待确认",
                "status_from_route_matrix": "继续看" if counts[route_id] else "待补证",
                "facts": {},
                "representative_asins": [],
                "operator_read": "从 review_asin_batch 聚合生成，需结合市场结构继续校验。",
            },
        )
        row["representative_asins"].append(item.get("asin"))
    return list(rows_by_route.values())


def normalize_route_row(row: dict[str, Any], review_batch: dict[str, Any], search: dict[str, Any]) -> dict[str, Any]:
    route_id = str(row.get("route_id") or row.get("id") or "")
    route_asins = [str(asin) for asin in as_list(row.get("representative_asins")) if str(asin).strip()]
    if not route_asins:
        route_asins = [
            str(item.get("asin"))
            for item in as_list(review_batch.get("asin_batch"))
            if isinstance(item, dict) and str(item.get("route") or "") == route_id and item.get("asin")
        ]
    keyword_refs = keyword_refs_for_route(search, route_id)
    return {
        "route_id": route_id,
        "route_name": row.get("route_name") or route_id or "未命名路线",
        "role_from_route_matrix": row.get("role_from_route_matrix") or row.get("role") or "",
        "status_from_route_matrix": row.get("status_from_route_matrix") or row.get("status") or "",
        "facts": row.get("facts") if isinstance(row.get("facts"), dict) else {},
        "representative_asins": route_asins,
        "keyword_refs": keyword_refs,
        "operator_read": row.get("operator_read") or row.get("why") or "路线已确认，仍需 VOC、代表 ASIN、关键词和小类目边界继续验证。",
        "source_refs": as_list(row.get("source_refs")) or ["market_structure.route_market_fit", "review_asin_batch"],
    }


def keyword_refs_for_route(search: dict[str, Any], route_id: str) -> list[str]:
    refs: list[str] = []
    roles = search.get("keyword_pool_by_role") if isinstance(search.get("keyword_pool_by_role"), dict) else {}
    for rows in roles.values():
        for item in as_list(rows):
            if not isinstance(item, dict):
                continue
            route_refs = [str(ref) for ref in as_list(item.get("route_refs"))]
            if route_id and route_id not in route_refs:
                continue
            keyword = str(item.get("keyword") or "").strip()
            if keyword and keyword not in refs:
                refs.append(keyword)
            if len(refs) >= 8:
                return refs
    return refs


def build_category_selection_derivation(
    workflow_state: dict[str, Any],
    review_batch: dict[str, Any],
    market: dict[str, Any],
    search: dict[str, Any],
    selected_route: str,
) -> dict[str, Any]:
    known_inputs = workflow_state.get("known_inputs") if isinstance(workflow_state.get("known_inputs"), dict) else {}
    category_candidates = as_list(search.get("category_candidates")) or as_list(market.get("category_candidates"))
    reference_asins = as_list(review_batch.get("asin_batch")) or as_list(search.get("reference_asin_inputs"))
    keyword_roles = search.get("keyword_pool_by_role") if isinstance(search.get("keyword_pool_by_role"), dict) else {}
    main_keywords = as_list(keyword_roles.get("main_traffic")) + as_list(keyword_roles.get("conversion_quality"))
    mixed_keywords = as_list(keyword_roles.get("mixed_or_excluded"))
    return {
        "selected_route": selected_route,
        "selected_category": selected_route,
        "confidence": "medium",
        "steps": [
            {
                "name": "用户约束",
                "evidence": compact_list([
                    known_inputs.get("scenario"),
                    known_inputs.get("site"),
                    join_text(known_inputs.get("constraints")),
                    known_inputs.get("price_preference"),
                ]),
                "decision": "只保留符合站点、使用场景和禁区的产品路线。",
                "lineage": ["workflow_state.known_inputs"],
            },
            {
                "name": "路线确认",
                "evidence": compact_list([
                    review_batch.get("candidate_name"),
                    join_text((review_batch.get("confirmed_boundary") or {}).get("keep_routes") if isinstance(review_batch.get("confirmed_boundary"), dict) else []),
                ]),
                "decision": "将已确认主线写入 route_matrix，旁支和混池不进入主推。",
                "lineage": ["review_asin_batch.confirmed_boundary"],
            },
            {
                "name": "类目和 ASIN 反推",
                "evidence": [
                    f"候选类目 {len(category_candidates)} 个",
                    f"参考 ASIN {len(reference_asins)} 个",
                ],
                "decision": "用代表 ASIN、类目候选和市场结构共同解释主线，不由单一关键词决定。",
                "lineage": ["search_demand.category_candidates", "market_structure.reference_asin_pool"],
            },
            {
                "name": "关键词交叉验证",
                "evidence": [
                    f"主/转化词 {len(main_keywords)} 条",
                    f"混池/排除词 {len(mixed_keywords)} 条",
                ],
                "decision": "主词用于验证需求，混池词用于定义排除边界。",
                "lineage": ["search_demand.keyword_pool_by_role"],
            },
        ],
        "rejected_alternatives": build_rejected_alternatives(review_batch, mixed_keywords),
        "disconfirming_evidence": [
            {
                "risk": "类目或关键词混池",
                "would_change_decision_if": "自然位主要由非目标产品形态、耗材、液体、配件或安装工具占据。",
                "next_check": "保留排除词，并用代表 ASIN 类目路径、搜索结果和 VOC 继续验证。",
            },
            {
                "risk": "VOC 痛点无法转成清晰产品方案",
                "would_change_decision_if": "评论痛点只指向泛体验问题，无法对应到规格、场景、包装或 Listing 风险提示。",
                "next_check": "补抓代表 ASIN 评论，并把高频痛点映射到具体规格、样品测试项或购买前提醒。",
            },
        ],
        "source_refs": [
            "workflow_state.known_inputs",
            "review_asin_batch.confirmed_boundary",
            "search_demand.keyword_pool_by_role",
            "market_structure.route_market_fit",
        ],
    }


def build_rejected_alternatives(review_batch: dict[str, Any], mixed_keywords: list[Any]) -> list[dict[str, Any]]:
    rows = []
    boundary = review_batch.get("confirmed_boundary") if isinstance(review_batch.get("confirmed_boundary"), dict) else {}
    for item in as_list(boundary.get("exclude_routes")):
        rows.append({"name": str(item), "decision": "排除", "reason": "不符合本轮确认边界。", "lineage": "review_asin_batch.confirmed_boundary"})
    for item in mixed_keywords[:5]:
        if isinstance(item, dict):
            rows.append({"name": item.get("keyword", ""), "decision": "混池观察/排除", "reason": item.get("reason", ""), "lineage": item.get("lineage", "search_demand.keyword_pool_by_role")})
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def path_ref(path: Path) -> str:
    return str(path) if path.exists() else f"missing:{path}"


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def join_text(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item).strip())
    return str(value or "").strip()


def compact_list(values: list[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build route_matrix_confirm.json for Stage 7.")
    parser.add_argument("run_dir", help="Run directory, for example runs/<run_id>.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = write_route_matrix_confirm(args.run_dir)
    print(f"route_matrix_confirm: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
