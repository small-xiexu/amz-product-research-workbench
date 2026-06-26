#!/usr/bin/env python3
"""Build P5 review VOC package — imports, normalizes, and structures review plugin exports.

Pure data tool: reads Excel/HTML/JSON from review plugins, normalizes fields,
computes stats, and writes a structured JSON. All VOC analysis is done by the
VOC Evidence Agent — not by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse existing parsing logic from the legacy script
from packages.research_core.pipeline.build_review_voc_from_plugin_export import (
    _build_stats,
    build_voc_package,
    normalize_review,
    read_ai_report,
    read_review_excel,
    read_reviews_from_json,
)
from packages.research_core.pipeline._utils import as_list, first_text, load_json, _run_id, _relative_path


P5_SCHEMA_VERSION = "p5-voc-gate-v1"
REVIEW_VOC_DIR = "review_voc"
VOC_PACKAGE_NAME = "review_voc_package.json"

P5_VOC_PACKAGE_INPUT_ARTIFACTS = [
    "workflow_state.json",
    "candidate_pool.json",
    "progress.json",
    "review_voc/review_asin_batch.json",
]
P5_VOC_PACKAGE_OUTPUT_ARTIFACTS = [
    f"{REVIEW_VOC_DIR}/{VOC_PACKAGE_NAME}",
]


class P5VocPackageError(Exception):
    """Raised when the VOC package cannot be built."""


def run_review_voc_package(
    run_dir: Path | str,
    *review_files: str | Path,
    json_input: str | Path | None = None,
) -> dict[str, Path]:
    """Build review_voc_package.json from review plugin exports."""
    run_path = Path(run_dir).expanduser().resolve()
    _validate_inputs(run_path)

    workflow_state = load_json(run_path / "workflow_state.json")
    progress = load_json(run_path / "progress.json")
    asin_batch_path = run_path / REVIEW_VOC_DIR / "review_asin_batch.json"
    asin_batch = load_json(asin_batch_path, required=False) if asin_batch_path.exists() else {}

    # Parse review inputs
    reviews, ai_reports, source_paths, parse_gaps = _parse_review_inputs(review_files, json_input)

    # Build the base package (reuses existing logic)
    candidate_id = _run_id(workflow_state, run_path)
    candidate_name = first_text(workflow_state.get("initial_intent") or "")
    package = build_voc_package(reviews, ai_reports, source_paths, candidate_id, candidate_name)

    # Enrich with P5 metadata
    package = _enrich_for_p5(package, run_path, workflow_state, asin_batch, parse_gaps)

    # Write output
    output_dir = run_path / REVIEW_VOC_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / VOC_PACKAGE_NAME
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Update progress
    progress_path = run_path / "progress.json"
    updated_progress = _update_progress(progress, package, package_path, run_path)
    progress_path.write_text(json.dumps(updated_progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "voc_package": package_path,
        "progress": progress_path,
    }


def _parse_review_inputs(
    review_files: tuple[str | Path, ...],
    json_input: str | Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path], list[dict[str, str]]]:
    reviews: list[dict[str, Any]] = []
    ai_reports: list[dict[str, Any]] = []
    source_paths: list[Path] = []
    gaps: list[dict[str, str]] = []

    if json_input:
        json_path = Path(json_input).expanduser().resolve()
        if not json_path.exists():
            raise P5VocPackageError(f"JSON input does not exist: {json_path}")
        try:
            reviews = read_reviews_from_json(json_path)
        except Exception as exc:
            raise P5VocPackageError(f"failed to read JSON input: {exc}") from exc
        source_paths = [json_path]
        if not reviews:
            gaps.append({"gap_type": "empty_json", "description": f"JSON input contains no review records: {json_path.name}", "impact": "no review data to analyze"})
        return reviews, ai_reports, source_paths, gaps

    if not review_files:
        raise P5VocPackageError("at least one review plugin export file is required, or use --json-input")

    input_paths = [Path(item).expanduser().resolve() for item in review_files]
    excel_paths = [p for p in input_paths if p.suffix.lower() == ".xlsx"]
    html_paths = [p for p in input_paths if p.suffix.lower() in {".html", ".htm"}]
    other_paths = [p for p in input_paths if p.suffix.lower() not in {".xlsx", ".html", ".htm"}]

    if not excel_paths and not other_paths:
        raise P5VocPackageError("at least one review plugin Excel export (.xlsx) is required")

    for path in excel_paths:
        if not path.exists():
            gaps.append({"gap_type": "file_missing", "description": f"review export file not found: {path}", "impact": "missing review source"})
            continue
        try:
            path_reviews = read_review_excel(path)
            reviews.extend(path_reviews)
            source_paths.append(path)
        except Exception as exc:
            gaps.append({"gap_type": "parse_error", "description": f"failed to parse {path.name}: {exc}", "impact": "review data from this file is unavailable"})

    for path in other_paths:
        if path.suffix.lower() == ".json":
            try:
                path_reviews = read_reviews_from_json(path)
                reviews.extend(path_reviews)
                source_paths.append(path)
            except Exception as exc:
                gaps.append({"gap_type": "parse_error", "description": f"failed to parse {path.name}: {exc}", "impact": "review data from this file is unavailable"})

    for path in html_paths:
        if not path.exists():
            gaps.append({"gap_type": "file_missing", "description": f"HTML report not found: {path}", "impact": "auxiliary reading reference missing"})
            continue
        try:
            ai_reports.append(read_ai_report(path))
            source_paths.append(path)
        except Exception as exc:
            gaps.append({"gap_type": "parse_error", "description": f"failed to parse HTML {path.name}: {exc}", "impact": "auxiliary reading reference unavailable"})

    if not reviews:
        gaps.append({"gap_type": "no_reviews", "description": "no reviews extracted from any input files", "impact": "VOC analysis not possible; need operator to re-export review data"})

    return reviews, ai_reports, source_paths, gaps


def _enrich_for_p5(
    package: dict[str, Any],
    run_path: Path,
    workflow_state: dict[str, Any],
    asin_batch: dict[str, Any],
    parse_gaps: list[dict[str, str]],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    run_id = _run_id(workflow_state, run_path)
    rel_batch_ref = _relative_path(asin_batch_ref_path(run_path), run_path)

    metadata = dict(package.get("metadata", {}))
    metadata["schema_version"] = P5_SCHEMA_VERSION
    metadata["run_id"] = run_id
    metadata["source_batch_ref"] = rel_batch_ref
    metadata["generated_at"] = now

    # Ensure stats has asin_distribution from normalized_reviews
    stats = dict(package.get("stats") or package.get("summary", {}))
    if "asin_count" not in stats:
        stats["asin_count"] = len(stats.get("asins", []))

    # Collect data gaps from parsing + post-hoc checks
    data_gaps = list(parse_gaps)
    normalized = list(package.get("normalized_reviews", []))

    # Check review count
    if len(normalized) < 30:
        data_gaps.append({
            "gap_type": "low_review_count",
            "description": f"only {len(normalized)} reviews (minimum 30 recommended for confident VOC analysis)",
            "impact": "VOC conclusions will have low confidence; consider capturing more reviews",
            "recommended_action": f"add {30 - len(normalized)}+ more reviews across target ASINs",
        })

    # Check low rating count
    low_count = sum(1 for r in normalized if (r.get("rating") if isinstance(r.get("rating"), (int, float)) else 0) <= 3)
    if low_count < 10 and len(normalized) > 0:
        data_gaps.append({
            "gap_type": "low_negative_review_count",
            "description": f"only {low_count} reviews with rating <= 3 (minimum 10 recommended)",
            "impact": "pain point analysis may miss negative signals",
        })

    # Check field completeness
    if normalized:
        missing_fields = _check_field_completeness(normalized)
        for field in missing_fields:
            data_gaps.append({
                "gap_type": "field_missing",
                "description": f"field '{field}' is missing in {missing_fields[field]} of {len(normalized)} reviews",
                "impact": "reduced traceability for VOC evidence",
            })

    # Compare covered ASINs against batch plan
    batch_asins = {item.get("asin", "") for item in as_list(asin_batch.get("asin_items")) if item.get("asin")}
    covered_asins = set(stats.get("asins", []))
    uncovered = batch_asins - covered_asins
    if uncovered:
        data_gaps.append({
            "gap_type": "uncovered_asins",
            "description": f"{len(uncovered)} ASIN(s) from batch plan have no reviews: {', '.join(sorted(uncovered)[:5])}",
            "impact": "route coverage may be incomplete for VOC analysis",
        })

    return {
        **package,
        "schema_version": P5_SCHEMA_VERSION,
        "metadata": metadata,
        "stats": stats,
        "summary": stats,
        "data_gaps": data_gaps,
        "pain_points": [],
        "highlights": [],
        "opportunity_hypotheses": [],
    }


def _check_field_completeness(normalized: list[dict[str, Any]]) -> dict[str, int]:
    missing: dict[str, int] = {}
    critical_fields = ["review_id", "asin", "rating", "review_date", "review_text", "review_text_zh", "url"]
    for field in critical_fields:
        count = sum(1 for r in normalized if not r.get(field))
        if count > 0:
            missing[field] = count
    return missing


def asin_batch_ref_path(run_path: Path) -> Path:
    return run_path / REVIEW_VOC_DIR / "review_asin_batch.json"


# ── Progress ───────────────────────────────────────────────────────────

def _update_progress(
    progress: dict[str, Any],
    package: dict[str, Any],
    package_path: Path,
    run_path: Path,
) -> dict[str, Any]:
    rel_path = _relative_path(package_path, run_path)
    stages = dict(progress.get("stages", {}))
    stage_7 = dict(stages.get("stage_7_voc_gate", {}))
    stage_7["status"] = "running"
    stage_7["updated_at"] = package.get("metadata", {}).get("generated_at", "")
    stages["stage_7_voc_gate"] = stage_7

    completed = list(progress.get("completed_artifacts", []))
    if rel_path not in completed:
        completed.append(rel_path)

    return {
        **progress,
        "current_stage": "stage_7_voc_gate",
        "stages": stages,
        "completed_artifacts": completed,
        "updated_at": package.get("metadata", {}).get("generated_at", ""),
        "next_action": {
            "type": "generate_voc_evidence",
            "description": "VOC package generated — proceed to VOC Evidence Agent analysis",
            "stage_id": "stage_7_voc_gate",
            "next_substage": "P5-3",
        },
    }


# ── Validation ─────────────────────────────────────────────────────────

def _validate_inputs(run_path: Path) -> None:
    for artifact in P5_VOC_PACKAGE_INPUT_ARTIFACTS:
        path = run_path / artifact
        if not path.exists():
            raise P5VocPackageError(f"required input not found: {artifact}")


# ── Helpers ────────────────────────────────────────────────────────────



# ── CLI ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build P5 review VOC package from review plugin exports."
    )
    parser.add_argument("run_dir", help="Path to the run directory.")
    parser.add_argument("inputs", nargs="*", help="Review plugin .xlsx exports and optional .html AI reports.")
    parser.add_argument("--json-input", dest="json_input", default=None, help="Review plugin JSON export (workbench mode).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outputs = run_review_voc_package(
            args.run_dir,
            *args.inputs,
            json_input=args.json_input,
        )
        package = json.loads(outputs["voc_package"].read_text(encoding="utf-8"))
        print(f"package: {outputs['voc_package']}")
        print(f"progress: {outputs['progress']}")
        print(f"reviews: {package['stats'].get('review_count', 0)}")
        print(f"asins: {package['stats'].get('asin_count', 0)}")
        print(f"low_rating: {package['stats'].get('low_rating_count', 0)}")
    except P5VocPackageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
