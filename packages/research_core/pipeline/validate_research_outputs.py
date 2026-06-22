from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


REQUIRED_FINAL_FILES = ("report.md", "report.html", "data.xlsx")
# 当前主链路 analysis/ 目录的预期文件（与 legacy final_report/ 五件套不同）
REQUIRED_ANALYSIS_FILES = ("analysis_report.html", "analysis_report.xlsx")
ANALYSIS_REQUIRED_SHEETS = (
    "Summary",
    "Source Packets",
    "Category Derivation",
    "Category Candidates",
    "Reference ASINs",
    "Keyword Pool",
    "VOC",
    "Route Judgment",
    "Risks And Next",
)
REQUIRED_WORKFLOW_FILES = ("workflow_summary.md", "workflow_summary.json")
BASE_REQUIRED_SHEETS = (
    "数据来源说明",
    "市场结构",
    "Top100原始明细",
    "数据质量检查",
    "属性定义",
    "Top商品打标",
    "待确认标签",
    "属性分布",
    "属性交叉分析",
    "机会判断",
    "竞品选择逻辑",
    "竞品池",
    "决策检查",
    "风险矩阵",
    "状态卡",
)
VOC_REQUIRED_SHEETS = ("评论VOC", "VOC证据")
REPORT_SECTION_TO_SHEETS = {
    "数据来源与口径": ("数据来源说明", "调研边界"),
    "市场结构与数据质量": ("市场结构", "Top100原始明细", "数据质量检查"),
    "产品属性分布与交叉分析": ("属性定义", "Top商品打标", "属性分布", "属性交叉分析", "机会判断"),
    "竞品池与竞品选择逻辑": ("竞品选择逻辑", "竞品池"),
    "评论 VOC 与真实痛点": ("评论VOC", "VOC证据"),
    "市场机会评分": ("市场机会评分卡", "决策检查", "风险矩阵", "状态卡"),
    "风险与待验证项": ("风险矩阵", "退货风险", "数据质量检查"),
    "继续研究优先级": ("市场机会评分卡", "路线深挖计划", "状态卡"),
    "下一步动作与证据附录": ("状态卡",),
}
REPORT_REQUIRED_TERMS = {
    "状态卡": ("状态卡",),
    "下一步": ("下一步",),
    "待补项": ("待补项", "待补"),
    "数据来源说明": ("数据来源说明", "数据来源"),
}
REPORT_QUALITY_TERMS = {
    "数据到行动建议": ("行动建议", "动作", "下一步"),
    "关键洞察": ("关键洞察", "AI 综合分析", "综合判断", "推断"),
    "事实推断区分": ("事实", "推断"),
    "验证动作": ("验证", "待补", "复核"),
}
ANALYSIS_MODE_TERMS = {
    "数据 -> 空白 -> 机会": ("空白", "机会"),
    "痛点 -> 产品方案": ("痛点", "产品方案", "规格"),
    "交叉维度 -> 结构性空白": ("交叉", "结构"),
    "多维评分 -> 优先级矩阵": ("评分卡", "优先级", "加权"),
    "待补项 -> 验证动作": ("待补", "验证", "复核"),
    "竞品角色 -> VOC 证据链": ("竞品", "VOC", "证据"),
    "数据点 -> 含义 -> 行动建议": ("数据点", "含义", "行动建议"),
}
ANALYSIS_MODE_SECTION_HINTS = {
    "数据 -> 空白 -> 机会": "市场结构与数据质量 / 产品属性分布与交叉分析",
    "痛点 -> 产品方案": "评论 VOC 与真实痛点",
    "交叉维度 -> 结构性空白": "产品属性分布与交叉分析",
    "多维评分 -> 优先级矩阵": "市场机会评分 / 继续研究优先级",
    "待补项 -> 验证动作": "下一步动作与证据附录",
    "竞品角色 -> VOC 证据链": "竞品池与竞品选择逻辑 / 评论 VOC 与真实痛点",
    "数据点 -> 含义 -> 行动建议": "Executive Summary / 当前结论",
}
from packages.report_renderer.constants import FORMAL_REPORT_SECTION_TITLES
INTERACTIVE_REPORT_REQUIRED_TERMS = (
    "交互式流程状态",
    "交互式下一步动作",
    "关键决策记录",
)
WAITING_TEMPLATE_TEXT = "待填写模板"
TOP100_EXPECTED_ROWS = 100
VOC_EVIDENCE_MIN_ROWS = 3
COMPETITOR_MIN_ROWS = 6
COMPETITOR_RECOMMENDED_ROWS = 10
COMPETITOR_MIN_ROLES = 4
REPORT_MIN_LINES = 200
EXECUTIVE_CHAIN_MIN_COUNT = 3
ATTRIBUTE_DISTRIBUTION_MIN_COUNT = 2
ANALYSIS_MODE_SELF_CHECK_MIN_USED = 3
REQUIRED_SCORECARD_DIMENSIONS = (
    "市场规模",
    "竞争格局",
    "需求清晰度",
    "新品友好度",
    "小类边界清晰度",
    "VOC证据质量",
    "退货/体验风险",
    "数据完整度",
)
@dataclass
class ValidationResult:
    workflow_dir: Path
    final_report_dir: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "workflow_dir": str(self.workflow_dir),
            "final_report_dir": str(self.final_report_dir),
            "errors": self.errors,
            "warnings": self.warnings,
            "notes": self.notes,
        }


def validate_workflow_output(input_dir: Path | str) -> ValidationResult:
    workflow_dir, final_report_dir = resolve_output_dirs(Path(input_dir).expanduser().resolve())
    result = ValidationResult(workflow_dir=workflow_dir, final_report_dir=final_report_dir)
    is_analysis_format = final_report_dir.name == "analysis"

    if is_analysis_format:
        _check_required_files(result, final_report_dir, REQUIRED_ANALYSIS_FILES, "analysis")
    else:
        _check_required_files(result, final_report_dir, REQUIRED_FINAL_FILES, "final_report")
    _check_required_files(result, workflow_dir, REQUIRED_WORKFLOW_FILES, "workflow")

    workflow_summary = _load_json(workflow_dir / "workflow_summary.json", result)
    report_text = _read_text(final_report_dir / ("analysis_report.html" if is_analysis_format else "report.md"))
    report_html = _read_text(final_report_dir / ("analysis_report.html" if is_analysis_format else "report.html"))

    sheet_names: set[str] = set()
    data_workbook = final_report_dir / ("analysis_report.xlsx" if is_analysis_format else "data.xlsx")
    if data_workbook.exists():
        sheet_names = _load_sheet_names(data_workbook, result)
        if is_analysis_format:
            _check_required_sheets(result, sheet_names, ANALYSIS_REQUIRED_SHEETS, "分析报告")
        else:
            _check_required_sheets(result, sheet_names, BASE_REQUIRED_SHEETS, "基础交付")
            _check_top100_rows(data_workbook, result)
            _check_attribute_analysis(data_workbook, result)
            _check_competitor_selection_logic(data_workbook, result)
            _check_go_nogo_scorecard(data_workbook, workflow_summary, result)
            _check_report_excel_traceability(sheet_names, result)

    if _review_voc_enabled(workflow_dir, workflow_summary) and not is_analysis_format:
        _check_required_sheets(result, sheet_names, VOC_REQUIRED_SHEETS, "评论 VOC")
        if data_workbook.exists():
            _check_voc_evidence_chain(data_workbook, result)

    if _interactive_workflow_enabled(workflow_summary) and not is_analysis_format:
        _check_required_sheets(result, sheet_names, ("交互决策记录",), "交互式流程")

    if is_analysis_format:
        _check_analysis_html_sections(result, report_html)
    else:
        _check_report_terms(result, report_text)
        _check_report_html(result, report_html)
        if _interactive_workflow_enabled(workflow_summary):
            _check_interactive_report_terms(result, report_text)
        _check_report_sections(result, report_text)
        _check_report_quality_terms(result, report_text)
        _check_analysis_mode_coverage(result, report_text)
        _check_quantitative_report_quality(result, report_text)
    return result


def resolve_output_dirs(path: Path) -> tuple[Path, Path]:
    # 路径本身就是 analysis/ 或 final_report/ 目录
    if path.is_dir() and path.name in ("analysis", "final_report"):
        return path.parent, path
    # 当前主链路：analysis/ 子目录
    if (path / "analysis").is_dir():
        return path, path / "analysis"
    # Legacy: final_report/ 子目录
    if (path / "final_report").is_dir():
        return path, path / "final_report"
    if (path / "report.md").exists() or (path / "data.xlsx").exists():
        return path.parent, path
    # 默认优先 analysis/
    return path, path / "analysis"


def render_result(result: ValidationResult) -> str:
    status = "通过" if result.ok else "失败"
    lines = [
        f"正式交付校验：{status}",
        f"- workflow_dir: {result.workflow_dir}",
        f"- final_report_dir: {result.final_report_dir}",
    ]
    if result.errors:
        lines.append("")
        lines.append("错误：")
        lines.extend(f"- {item}" for item in result.errors)
    if result.warnings:
        lines.append("")
        lines.append("警告：")
        lines.extend(f"- {item}" for item in result.warnings)
    if result.notes:
        lines.append("")
        lines.append("检查记录：")
        lines.extend(f"- {item}" for item in result.notes)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate formal product research workflow outputs.")
    parser.add_argument("workflow_output_dir", help="run_research_workflow.py generated output directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation result.")
    args = parser.parse_args(argv)

    result = validate_workflow_output(args.workflow_output_dir)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_result(result), end="")
    return 0 if result.ok else 1


def _check_required_files(result: ValidationResult, base_dir: Path, filenames: tuple[str, ...], label: str) -> None:
    for filename in filenames:
        path = base_dir / filename
        if path.exists():
            result.notes.append(f"{label} 文件存在：{filename}")
        else:
            result.errors.append(f"{label} 缺少必需文件：{path}")


def _load_json(path: Path, result: ValidationResult) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.errors.append(f"workflow_summary.json 不是合法 JSON：{exc}")
        return {}
    if isinstance(data, dict):
        return data
    result.errors.append("workflow_summary.json 根节点必须是对象")
    return {}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _load_sheet_names(path: Path, result: ValidationResult) -> set[str]:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:  # pragma: no cover - openpyxl error types vary by file corruption mode
        result.errors.append(f"data.xlsx 无法读取：{exc}")
        return set()
    try:
        sheet_names = set(workbook.sheetnames)
        result.notes.append(f"data.xlsx 可读取，Sheet 数：{len(sheet_names)}")
        return sheet_names
    finally:
        workbook.close()


def _check_required_sheets(
    result: ValidationResult,
    sheet_names: set[str],
    required_sheets: tuple[str, ...],
    label: str,
) -> None:
    if not sheet_names:
        return
    missing = [name for name in required_sheets if name not in sheet_names]
    if missing:
        result.errors.append(f"{label} 缺少关键 Sheet：{', '.join(missing)}")
    else:
        result.notes.append(f"{label} 关键 Sheet 完整")


def _check_top100_rows(path: Path, result: ValidationResult) -> None:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return
    try:
        if "Top100原始明细" not in workbook.sheetnames:
            return
        row_count = _count_data_rows(workbook["Top100原始明细"])
    finally:
        workbook.close()
    if row_count < TOP100_EXPECTED_ROWS:
        result.warnings.append(f"Top100原始明细有效商品行数为 {row_count}，低于正式深挖建议的 {TOP100_EXPECTED_ROWS} 行")
    else:
        result.notes.append(f"Top100原始明细有效商品行数：{row_count}")


def _check_attribute_analysis(path: Path, result: ValidationResult) -> None:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return
    try:
        definitions = _count_data_rows(workbook["属性定义"]) if "属性定义" in workbook.sheetnames else 0
        cross_count = _count_group_rows(workbook["属性交叉分析"]) if "属性交叉分析" in workbook.sheetnames else 0
        opportunity_count = _count_data_rows(workbook["机会判断"]) if "机会判断" in workbook.sheetnames else 0
    finally:
        workbook.close()
    if definitions < 3:
        result.errors.append(f"属性定义少于 3 个核心维度：当前 {definitions} 个")
    else:
        result.notes.append(f"属性定义核心维度数：{definitions}")
    if cross_count < 3:
        result.errors.append(f"属性交叉分析少于 3 组：当前 {cross_count} 组")
    else:
        result.notes.append(f"属性交叉分析组数：{cross_count}")
    if opportunity_count < 1:
        result.errors.append("机会判断 Sheet 缺少真机会/伪机会/待验证记录")
    else:
        result.notes.append(f"机会判断记录数：{opportunity_count}")


def _check_competitor_selection_logic(path: Path, result: ValidationResult) -> None:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return
    try:
        if "竞品选择逻辑" not in workbook.sheetnames:
            return
        rows = list(workbook["竞品选择逻辑"].iter_rows(values_only=True))
    finally:
        workbook.close()
    if len(rows) <= 1:
        result.errors.append("竞品选择逻辑 Sheet 为空")
        return
    header = [str(item or "") for item in rows[0]]
    required = ["ASIN", "品牌", "价格", "月销量", "评分", "评分数", "竞品类型", "覆盖维度", "选择理由"]
    missing_headers = [item for item in required if not any(item in cell for cell in header)]
    if missing_headers:
        result.errors.append(f"竞品选择逻辑缺少字段：{', '.join(missing_headers)}")
        return
    data_rows = [row for row in rows[1:] if row and str(row[0] or "").strip() not in {"", "未生成"}]
    if not data_rows:
        result.errors.append("竞品选择逻辑缺少有效竞品行")
        return
    role_values = {str(row[7] or "") for row in data_rows if len(row) > 7}
    if len(data_rows) < COMPETITOR_MIN_ROWS:
        result.errors.append(f"竞品选择逻辑有效行少于 {COMPETITOR_MIN_ROWS} 行：当前 {len(data_rows)} 行")
    elif len(data_rows) < COMPETITOR_RECOMMENDED_ROWS:
        result.warnings.append(
            f"竞品选择逻辑有效行少于 Zach 标准建议的 {COMPETITOR_RECOMMENDED_ROWS} 行：当前 {len(data_rows)} 行"
        )
    if len(role_values) < COMPETITOR_MIN_ROLES:
        result.warnings.append(f"竞品选择逻辑覆盖角色少于 {COMPETITOR_MIN_ROLES} 类：{', '.join(sorted(role_values)) or '无'}")
    result.notes.append(f"竞品选择逻辑有效行数：{len(data_rows)}")


def _check_voc_evidence_chain(path: Path, result: ValidationResult) -> None:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return
    try:
        if "VOC证据" not in workbook.sheetnames:
            return
        rows = list(workbook["VOC证据"].iter_rows(values_only=True))
    finally:
        workbook.close()
    if len(rows) <= 1:
        result.errors.append("VOC证据 Sheet 为空，评论接入后必须保留 review_id、ASIN、评分和片段")
        return
    header = [str(item or "") for item in rows[0]]
    required = ["评论ID", "ASIN", "评分", "证据片段"]
    missing_headers = [item for item in required if item not in header]
    if missing_headers:
        result.errors.append(f"VOC证据缺少追溯字段：{', '.join(missing_headers)}")
        return
    indexes = {name: header.index(name) for name in required}
    valid_rows = 0
    incomplete_rows = 0
    for row in rows[1:]:
        if not row or str(row[0] or "").strip() == "未接入":
            continue
        values = [row[indexes[name]] if indexes[name] < len(row) else None for name in required]
        if all(str(value or "").strip() for value in values):
            valid_rows += 1
        else:
            incomplete_rows += 1
    if valid_rows == 0:
        result.errors.append("VOC证据缺少完整可追溯行：review_id、ASIN、评分、片段必须同时存在")
    elif valid_rows < VOC_EVIDENCE_MIN_ROWS:
        result.warnings.append(f"VOC证据完整追溯行少于 {VOC_EVIDENCE_MIN_ROWS} 行：当前 {valid_rows} 行")
    if incomplete_rows:
        result.warnings.append(f"VOC证据存在 {incomplete_rows} 行追溯字段不完整")
    result.notes.append(f"VOC证据完整追溯行数：{valid_rows}")


def _check_go_nogo_scorecard(path: Path, workflow_summary: dict[str, Any], result: ValidationResult) -> None:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return
    try:
        if "市场机会评分卡" not in workbook.sheetnames:
            return
        rows = list(workbook["市场机会评分卡"].iter_rows(values_only=True))
    finally:
        workbook.close()
    dimension_names = {str(row[0] or "") for row in rows[1:] if row and str(row[0] or "") in REQUIRED_SCORECARD_DIMENSIONS}
    missing = [name for name in REQUIRED_SCORECARD_DIMENSIONS if name not in dimension_names]
    if missing:
        result.errors.append(f"市场机会评分卡缺少固定维度：{', '.join(missing)}")
    else:
        result.notes.append("市场机会评分卡固定维度完整")
    decision = ""
    gating_text = ""
    for row in rows:
        if row and row[0] == "决策结论":
            decision = str(row[1] or "")
        if row and row[0] == "决策限制":
            gating_text = str(row[1] or "")
    if gating_text and decision.upper() == "GO":
        result.errors.append("市场机会评分仍有证据缺口时禁止输出 GO")


def _count_data_rows(sheet: Any) -> int:
    count = 0
    for row in sheet.iter_rows(min_row=2, values_only=True):
        values = [str(cell).strip() for cell in row if cell not in (None, "")]
        if not values:
            continue
        if all(value in {"待填", "未生成", "未接入"} for value in values):
            continue
        count += 1
    return count


def _count_group_rows(sheet: Any) -> int:
    count = 0
    for row in sheet.iter_rows(min_row=2, values_only=True):
        first_cell = str(row[0]).strip() if row and row[0] not in (None, "") else ""
        if first_cell and first_cell not in {"待填", "未生成", "未接入"}:
            count += 1
    return count


def _review_voc_enabled(workflow_dir: Path, workflow_summary: dict[str, Any]) -> bool:
    review_voc = _section(workflow_summary, "review_voc")
    return bool(review_voc.get("enabled")) or (workflow_dir / "review_voc_package.json").exists()


def _interactive_workflow_enabled(workflow_summary: dict[str, Any]) -> bool:
    interactive = _section(workflow_summary, "interactive_workflow")
    return bool(interactive.get("enabled"))


def _section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _check_waiting_template_status(
    result: ValidationResult,
    section: dict[str, Any],
    workflow_summary_text: str,
    label: str,
) -> None:
    status = str(section.get("status", ""))
    if WAITING_TEMPLATE_TEXT in status or WAITING_TEMPLATE_TEXT in workflow_summary_text:
        result.notes.append(f"{label} 未回填状态已明确：{WAITING_TEMPLATE_TEXT}")
    else:
        result.errors.append(f"{label} 未回填时必须在 workflow_summary 中明确“{WAITING_TEMPLATE_TEXT}”")


def _check_report_terms(result: ValidationResult, report_text: str) -> None:
    if not report_text:
        return
    missing = [label for label, terms in REPORT_REQUIRED_TERMS.items() if not any(term in report_text for term in terms)]
    if missing:
        result.errors.append(f"report.md 缺少正式交付锚点：{', '.join(missing)}")
    else:
        result.notes.append("report.md 已包含状态卡、下一步、待补项和数据来源说明")


def _check_report_excel_traceability(sheet_names: set[str], result: ValidationResult) -> None:
    if not sheet_names:
        return
    missing: list[str] = []
    for section, sheets in REPORT_SECTION_TO_SHEETS.items():
        missing_sheets = [sheet for sheet in sheets if sheet not in sheet_names]
        if missing_sheets:
            missing.append(f"{section} -> {', '.join(missing_sheets)}")
    if missing:
        result.errors.append(f"报告章节缺少 Excel 回表 Sheet：{'; '.join(missing)}")
    else:
        result.notes.append("报告章节到 Excel Sheet 的回表关系完整")


def _check_report_quality_terms(result: ValidationResult, report_text: str) -> None:
    if not report_text:
        return
    missing = [
        label
        for label, terms in REPORT_QUALITY_TERMS.items()
        if not any(term in report_text for term in terms)
    ]
    if missing:
        result.warnings.append(f"report.md 缺少 Zach 式报告质量提示词：{', '.join(missing)}")
    else:
        result.notes.append("report.md 已覆盖数据点、洞察、事实推断和验证动作等质量门槛")


def _check_analysis_mode_coverage(result: ValidationResult, report_text: str) -> None:
    if not report_text:
        return
    matched = [
        label
        for label, terms in ANALYSIS_MODE_TERMS.items()
        if all(term in report_text for term in terms)
    ]
    if len(matched) < 3:
        missing = [label for label in ANALYSIS_MODE_TERMS if label not in matched]
        suggestions = [
            f"{label} -> {ANALYSIS_MODE_SECTION_HINTS.get(label, '对应章节')}"
            for label in missing[:4]
        ]
        result.errors.append(
            "report.md 可识别的分析模式少于 3 种，当前为 "
            + (", ".join(matched) if matched else "未识别")
            + "；建议补充："
            + "；".join(suggestions)
        )
    else:
        result.notes.append(f"report.md 可识别分析模式：{', '.join(matched[:6])}")


def _check_quantitative_report_quality(result: ValidationResult, report_text: str) -> None:
    if not report_text:
        return
    line_count = len([line for line in report_text.splitlines() if line.strip()])
    if line_count < REPORT_MIN_LINES:
        result.errors.append(f"report.md 总行数少于 {REPORT_MIN_LINES} 行：当前 {line_count} 行")
    else:
        result.notes.append(f"report.md 总行数：{line_count}")

    executive = _section_text(report_text, "Executive Summary / 当前结论")
    chain_count = _executive_chain_count(executive)
    if chain_count < EXECUTIVE_CHAIN_MIN_COUNT:
        result.errors.append(
            f"Executive Summary 中 `数据点 -> 含义 -> 行动建议` 链条少于 {EXECUTIVE_CHAIN_MIN_COUNT} 条：当前 {chain_count} 条"
        )
    else:
        result.notes.append(f"Executive Summary 结论链条数：{chain_count}")

    attribute_section = _section_text(report_text, "产品属性分布与交叉分析")
    distribution_count = _attribute_distribution_count(attribute_section)
    if distribution_count < ATTRIBUTE_DISTRIBUTION_MIN_COUNT:
        result.errors.append(
            f"产品属性分布小节少于 {ATTRIBUTE_DISTRIBUTION_MIN_COUNT} 项：当前 {distribution_count} 项"
        )
    else:
        result.notes.append(f"产品属性分布小节数：{distribution_count}")

    used_modes = _analysis_mode_self_check_used_count(report_text)
    if used_modes < ANALYSIS_MODE_SELF_CHECK_MIN_USED:
        result.errors.append(
            f"分析模式自检表 `已用` 行少于 {ANALYSIS_MODE_SELF_CHECK_MIN_USED} 行：当前 {used_modes} 行"
        )
    else:
        result.notes.append(f"分析模式自检表已用行数：{used_modes}")


def _section_text(report_text: str, title: str) -> str:
    marker = f"## {title}"
    start = report_text.find(marker)
    if start < 0:
        return ""
    next_start = report_text.find("\n## ", start + len(marker))
    if next_start < 0:
        return report_text[start:]
    return report_text[start:next_start]


def _executive_chain_count(section_text: str) -> int:
    count = 0
    for line in section_text.splitlines():
        if "数据点" in line and "含义" in line and "行动建议" in line:
            count += 1
    return max(0, count - 1) if "### 数据点 -> 含义 -> 行动建议" in section_text else count


def _attribute_distribution_count(section_text: str) -> int:
    in_distribution = False
    count = 0
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("### 属性分布"):
            in_distribution = True
            continue
        if in_distribution and stripped.startswith("### "):
            break
        if in_distribution and stripped.startswith("- ") and "：" in stripped and "未生成" not in stripped:
            count += 1
    return count


def _analysis_mode_self_check_used_count(report_text: str) -> int:
    section = report_text[report_text.find("### 分析模式自检表"):] if "### 分析模式自检表" in report_text else ""
    count = 0
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and "| 已用 |" in stripped:
            count += 1
    return count


def _check_report_html(result: ValidationResult, report_html: str) -> None:
    if not report_html:
        result.errors.append("report.html 内容为空或不存在")
        return
    required_terms = (
        "<!doctype html>",
        '<html lang="zh-CN">',
        "选品决策报告",
        "一眼看懂",
        "市场机会评分",
    )
    missing = [term for term in required_terms if term not in report_html]
    if missing:
        result.errors.append(f"report.html 缺少关键内容：{', '.join(missing)}")
    else:
        result.notes.append("report.html 已生成选品决策报告")


def _check_interactive_report_terms(result: ValidationResult, report_text: str) -> None:
    missing = [term for term in INTERACTIVE_REPORT_REQUIRED_TERMS if term not in report_text]
    if missing:
        result.errors.append(f"report.md 缺少交互式流程锚点：{', '.join(missing)}")
    else:
        result.notes.append("report.md 已包含交互式流程状态、下一步动作和关键决策记录")


def _check_report_sections(result: ValidationResult, report_text: str) -> None:
    if not report_text:
        return
    positions: list[int] = []
    missing: list[str] = []
    for title in FORMAL_REPORT_SECTION_TITLES:
        marker = f"## {title}"
        position = report_text.find(marker)
        if position < 0:
            missing.append(title)
        else:
            positions.append(position)
    if missing:
        result.errors.append(f"report.md 缺少正式章节：{', '.join(missing)}")
        return
    if positions != sorted(positions):
        result.errors.append("report.md 正式章节顺序不符合 P20.2 标准")
        return
    result.notes.append("report.md 正式 12 章结构完整且顺序正确")


ANALYSIS_HTML_SECTION_MARKERS = (
    "类目全景",
    "数据来源与口径",
    "核心竞品",
    "用户痛点",
    "价格带分布",
    "关键词与流量策略",
    "风险与下一步",
)


def _check_analysis_html_sections(result: ValidationResult, report_html: str) -> None:
    if not report_html:
        result.errors.append("analysis_report.html 为空")
        return
    missing = [m for m in ANALYSIS_HTML_SECTION_MARKERS if m not in report_html]
    if missing:
        result.errors.append(f"analysis_report.html 缺少板块：{', '.join(missing)}")
    else:
        result.notes.append("analysis_report.html 8 板块完整")
    if 'class="go-nogo"' not in report_html and "class='go-nogo'" not in report_html:
        result.warnings.append("analysis_report.html Go/No-Go 表缺少 .go-nogo class")
    if "<style>" in report_html:
        result.errors.append("analysis_report.html 含内联 <style>，应 <link> 引用 report_template.css")


if __name__ == "__main__":
    raise SystemExit(main())
