"""Application workflow from manual exports to final research outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from packages.report_renderer.render_report import build_outputs
from packages.research_core.contracts import (
    validate_candidate_pool,
    validate_import_manifest,
    validate_research_package,
    validate_review_voc_package,
    validate_workflow_state,
)
from packages.research_core.pipeline.apply_ip_compliance_review import apply_ip_compliance_review, read_ip_compliance_review
from packages.research_core.pipeline.apply_profit_review import apply_profit_review, read_profit_inputs
from packages.research_core.pipeline.build_candidate_pool_from_import_manifest import build_candidate_pool
from packages.research_core.pipeline.build_ip_compliance_template import render_ip_compliance_template
from packages.research_core.pipeline.build_profit_template import render_profit_template
from packages.research_core.pipeline.build_research_package_from_candidate import build_research_package
from packages.research_core.pipeline.build_review_voc_from_plugin_export import (
    build_voc_package,
    read_ai_report,
    read_review_excel,
    render_markdown as render_voc_markdown,
    render_summary as render_voc_summary,
    render_workbook as render_voc_workbook,
)
from packages.research_core.pipeline.inspect_manual_exports import build_manifest


@dataclass(frozen=True)
class WorkflowConfig:
    manual_export_folder: Path
    output_dir: Path
    site: str = "US"
    task_name: str = ""
    candidate_id: str = ""
    candidate_name: str = ""
    review_inputs: tuple[Path, ...] = ()
    profit_template: Path | None = None
    ip_compliance_template: Path | None = None
    sorftime_verification: Path | None = None
    workflow_state: Path | None = None


@dataclass(frozen=True)
class WorkflowResult:
    output_dir: Path
    final_report_dir: Path
    selected_candidate_id: str
    selected_candidate_name: str
    manifest_path: Path
    candidate_pool_path: Path
    research_package_path: Path
    workflow_summary_path: Path
    workflow_summary_json_path: Path

    @property
    def report_path(self) -> Path:
        return self.final_report_dir / "report.md"


def run_research_workflow(config: WorkflowConfig) -> WorkflowResult:
    export_folder = config.manual_export_folder.expanduser().resolve()
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not export_folder.exists() or not export_folder.is_dir():
        raise ValueError(f"Manual export folder does not exist or is not a directory: {export_folder}")

    manifest = build_manifest(export_folder, config.task_name or export_folder.name, config.site)
    validate_import_manifest(manifest)
    manifest_path = output_dir / "import_manifest.json"
    write_json(manifest_path, manifest)

    sorftime_verification = _load_optional_json(config.sorftime_verification, "Sorftime verification")
    candidate_pool = build_candidate_pool(manifest, sorftime_verification=sorftime_verification)
    validate_candidate_pool(candidate_pool)
    candidate_pool_path = output_dir / "candidate_pool.json"
    write_json(candidate_pool_path, candidate_pool)

    candidate = select_candidate(candidate_pool, config.candidate_id)
    candidate_id = str(candidate.get("candidate_id", ""))
    candidate_name = config.candidate_name or str(candidate.get("name", ""))

    review_inputs = tuple(path.expanduser().resolve() for path in config.review_inputs)
    voc_package = (
        build_review_outputs(output_dir / "review_voc", list(review_inputs), candidate_id, candidate_name)
        if review_inputs
        else None
    )
    validate_review_voc_package(voc_package)

    research_package = build_research_package(candidate_pool, candidate_id, voc_package)
    validate_research_package(research_package)

    profit_template_path = output_dir / "profit_review_template.xlsx"
    render_profit_template(research_package, profit_template_path)
    profit_inputs = read_profit_inputs(config.profit_template.expanduser().resolve()) if config.profit_template else None
    if profit_inputs is not None:
        research_package = apply_profit_review(research_package, profit_inputs)
        validate_research_package(research_package)

    ip_compliance_template_path = output_dir / "ip_compliance_review_template.xlsx"
    render_ip_compliance_template(research_package, ip_compliance_template_path)
    ip_compliance_review = (
        read_ip_compliance_review(config.ip_compliance_template.expanduser().resolve())
        if config.ip_compliance_template
        else None
    )
    if ip_compliance_review is not None:
        research_package = apply_ip_compliance_review(research_package, ip_compliance_review)
        validate_research_package(research_package)

    workflow_state = _load_optional_json(config.workflow_state, "Workflow state")
    if workflow_state is not None:
        validate_workflow_state(workflow_state)
        research_package["workflow_trace"] = build_workflow_trace(workflow_state, config.workflow_state)
        validate_research_package(research_package)

    research_package_path = output_dir / "research_package.json"
    write_json(research_package_path, research_package)

    final_report_dir = output_dir / "final_report"
    build_outputs(str(research_package_path), str(final_report_dir))

    workflow_summary = build_workflow_summary(
        output_dir=output_dir,
        manifest=manifest,
        candidate=candidate,
        voc_package=voc_package,
        final_report_dir=final_report_dir,
        research_package=research_package,
        profit_template_path=profit_template_path,
        profit_applied=profit_inputs is not None,
        ip_compliance_template_path=ip_compliance_template_path,
        ip_compliance_applied=ip_compliance_review is not None,
        workflow_trace=research_package.get("workflow_trace", {}),
    )
    workflow_summary_json_path = output_dir / "workflow_summary.json"
    workflow_summary_path = output_dir / "workflow_summary.md"
    write_json(workflow_summary_json_path, workflow_summary)
    workflow_summary_path.write_text(render_workflow_summary(workflow_summary), encoding="utf-8")

    return WorkflowResult(
        output_dir=output_dir,
        final_report_dir=final_report_dir,
        selected_candidate_id=candidate_id,
        selected_candidate_name=candidate_name,
        manifest_path=manifest_path,
        candidate_pool_path=candidate_pool_path,
        research_package_path=research_package_path,
        workflow_summary_path=workflow_summary_path,
        workflow_summary_json_path=workflow_summary_json_path,
    )


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_candidate(candidate_pool: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    candidates = candidate_pool.get("candidates", [])
    if not candidates:
        raise ValueError("candidate_pool has no candidates")
    if candidate_id:
        for candidate in candidates:
            if candidate.get("candidate_id") == candidate_id:
                return candidate
        raise ValueError(f"candidate_id not found: {candidate_id}")
    return candidates[0]


def build_review_outputs(
    output_dir: Path,
    input_paths: list[Path],
    candidate_id: str,
    candidate_name: str,
) -> dict[str, Any]:
    excel_paths = [path for path in input_paths if path.suffix.lower() == ".xlsx"]
    html_paths = [path for path in input_paths if path.suffix.lower() in {".html", ".htm"}]
    if not excel_paths:
        raise ValueError("--review-input 至少需要包含一个评论插件 Excel 文件")
    for path in input_paths:
        if not path.exists() or not path.is_file():
            raise ValueError(f"Review input does not exist or is not a file: {path}")

    reviews: list[dict[str, Any]] = []
    for path in excel_paths:
        reviews.extend(read_review_excel(path))
    ai_reports = [read_ai_report(path) for path in html_paths]
    package = build_voc_package(reviews, ai_reports, input_paths, candidate_id, candidate_name)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "review_voc_package.json", package)
    (output_dir / "voc_report.md").write_text(render_voc_markdown(package), encoding="utf-8")
    (output_dir / "voc_summary.md").write_text(render_voc_summary(package), encoding="utf-8")
    render_voc_workbook(package, output_dir / "voc_evidence.xlsx")
    return package


def build_workflow_summary(
    output_dir: Path,
    manifest: dict[str, Any],
    candidate: dict[str, Any],
    voc_package: dict[str, Any] | None,
    final_report_dir: Path,
    research_package: dict[str, Any],
    profit_template_path: Path,
    profit_applied: bool,
    ip_compliance_template_path: Path,
    ip_compliance_applied: bool,
    workflow_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data_quality = manifest.get("data_quality", {})
    voc_summary = voc_package.get("summary", {}) if voc_package else {}
    profit_review = research_package.get("profit_review", {}) if profit_applied else {}
    ip_compliance_review = research_package.get("ip_compliance_review", {}) if ip_compliance_applied else {}
    workflow_state = workflow_trace.get("workflow_state", {}) if isinstance(workflow_trace, dict) else {}
    decision_log = workflow_trace.get("decision_log", []) if isinstance(workflow_trace, dict) else []
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "selected_candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "name": candidate.get("name"),
            "status": candidate.get("status"),
        },
        "seller_sprite_sources": {
            "available": data_quality.get("available_source_types", []),
            "missing": data_quality.get("missing_source_types", []),
            "warnings": data_quality.get("warnings", []),
        },
        "review_voc": {
            "enabled": bool(voc_package),
            "review_count": voc_summary.get("review_count", 0),
            "asin_count": voc_summary.get("asin_count", 0),
            "low_rating_count": voc_summary.get("low_rating_count", 0),
        },
        "profit_review": {
            "template": str(profit_template_path),
            "applied": profit_applied,
            "status": profit_review.get("status") if profit_applied else "待填写模板",
            "missing_fields": profit_review.get("missing_fields", []) if profit_applied else [],
        },
        "ip_compliance_review": {
            "template": str(ip_compliance_template_path),
            "applied": ip_compliance_applied,
            "status": ip_compliance_review.get("status") if ip_compliance_applied else "待填写模板",
            "overall_level": ip_compliance_review.get("overall_level") if ip_compliance_applied else "待复核",
            "missing_fields": ip_compliance_review.get("missing_fields", []) if ip_compliance_applied else [],
            "pending_fields": ip_compliance_review.get("pending_fields", []) if ip_compliance_applied else [],
        },
        "interactive_workflow": {
            "enabled": bool(workflow_state),
            "workflow_id": workflow_state.get("workflow_id"),
            "mode": workflow_state.get("mode"),
            "stage": workflow_state.get("stage"),
            "decision_count": len(decision_log) if isinstance(decision_log, list) else 0,
            "source_file": workflow_trace.get("source_file") if isinstance(workflow_trace, dict) else "",
        },
        "outputs": {
            "import_manifest": str(output_dir / "import_manifest.json"),
            "candidate_pool": str(output_dir / "candidate_pool.json"),
            "research_package": str(output_dir / "research_package.json"),
            "profit_template": str(profit_template_path),
            "ip_compliance_template": str(ip_compliance_template_path),
            "final_report": str(final_report_dir / "report.md"),
            "summary": str(final_report_dir / "summary.md"),
            "dashboard": str(final_report_dir / "dashboard.html"),
            "data_workbook": str(final_report_dir / "data.xlsx"),
        },
    }


def render_workflow_summary(summary: dict[str, Any]) -> str:
    candidate = summary["selected_candidate"]
    sources = summary["seller_sprite_sources"]
    voc = summary["review_voc"]
    profit = summary["profit_review"]
    ip_compliance = summary["ip_compliance_review"]
    interactive = summary.get("interactive_workflow", {})
    outputs = summary["outputs"]
    lines = [
        "# 选品流程运行摘要",
        "",
        f"- 候选方向：{candidate.get('candidate_id')} / {candidate.get('name')} / {candidate.get('status')}",
        f"- 卖家精灵来源：{', '.join(sources.get('available', [])) or '无'}",
        f"- 缺失来源：{', '.join(sources.get('missing', [])) or '无'}",
        f"- 评论 VOC：{'已接入' if voc.get('enabled') else '未接入'}",
        f"- 利润复核：{profit.get('status') if profit.get('applied') else '待填写模板'}",
        f"- 知产/合规初筛：{ip_compliance.get('status') if ip_compliance.get('applied') else '待填写模板'}"
        + (f" / 整体风险 {ip_compliance.get('overall_level')}" if ip_compliance.get("applied") else ""),
    ]
    if interactive.get("enabled"):
        lines.append(
            f"- 交互式流程：{interactive.get('workflow_id')} / {interactive.get('mode')} / "
            f"{interactive.get('stage')}，决策记录 {interactive.get('decision_count', 0)} 条"
        )
    if profit.get("missing_fields"):
        lines.append(f"- 利润待补：{', '.join(profit.get('missing_fields', []))}")
    unresolved_ip = [*ip_compliance.get("missing_fields", []), *ip_compliance.get("pending_fields", [])]
    if unresolved_ip:
        lines.append(f"- 知产/合规待补或待复核：{', '.join(str(item) for item in unresolved_ip)}")
    if voc.get("enabled"):
        lines.extend(
            [
                f"- 评论数：{voc.get('review_count', 0)}",
                f"- ASIN 数：{voc.get('asin_count', 0)}",
                f"- 低分评论数：{voc.get('low_rating_count', 0)}",
            ]
        )
    lines.extend(["", "## 输出文件"])
    for label, path in outputs.items():
        lines.append(f"- {label}: `{path}`")
    return "\n".join(lines) + "\n"


def build_workflow_trace(workflow_state: dict[str, Any], source_path: Path | None = None) -> dict[str, Any]:
    state = dict(workflow_state)
    decision_log = list(state.get("decision_log", []))
    next_actions = list(state.get("next_actions", []))
    evidence_refs = list(state.get("evidence_refs", []))
    return {
        "workflow_state": state,
        "decision_log": decision_log,
        "next_actions": next_actions,
        "evidence_refs": evidence_refs,
        "source_file": str(source_path.expanduser().resolve()) if source_path else "",
    }


def _load_optional_json(path: Path | None, label: str) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"{label} file does not exist: {resolved}")
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} file must contain a JSON object: {resolved}")
    return data
