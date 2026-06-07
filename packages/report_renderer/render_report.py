"""Render a minimal research report from a research package."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape as xml_escape


def render_markdown(package: dict) -> str:
    meta = package.get("metadata", {})
    market = package.get("market_analysis", {})
    profit = package.get("profit_reference", {})
    status = package.get("status_card", {})

    lines = [
        f"# {meta.get('seed_keyword_or_category', '未命名品类')} 调研报告",
        "",
        "## 结论摘要",
        f"- 状态：{status.get('status', '待填')}",
        f"- 理由：{status.get('reason', '待填')}",
        "",
        "## 市场扫描",
        f"- 市场规模：{market.get('market_size', '待填')}",
        f"- 价格带：{market.get('price_band', '待填')}",
        "",
        "## 利润参考",
        f"- 基础 FBA 毛利：{profit.get('base_fba_gross_profit', '待填')}",
        f"- 扣广告和退货后的 FBA 毛利：{profit.get('post_ads_returns_gross_profit', '待填')}",
        "",
    ]
    return "\n".join(lines)


def render_summary(package: dict) -> str:
    status = package.get("status_card", {})
    return "\n".join(
        [
            "# 摘要",
            "",
            f"- 状态：{status.get('status', '待填')}",
            f"- 原因：{status.get('reason', '待填')}",
            f"- 下一步：{status.get('next_step', '待填')}",
        ]
    )


def render_dashboard(package: dict) -> str:
    meta = package.get("metadata", {})
    market = package.get("market_analysis", {})
    profit = package.get("profit_reference", {})
    title = escape(str(meta.get("seed_keyword_or_category", "调研看板")))
    site = escape(str(meta.get("site", "待填")))
    market_size = escape(str(market.get("market_size", "待填")))
    price_band = escape(str(market.get("price_band", "待填")))
    base_profit = escape(str(profit.get("base_fba_gross_profit", "待填")))

    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <h1>{title}</h1>
  <ul>
    <li>站点：{site}</li>
    <li>市场规模：{market_size}</li>
    <li>价格带：{price_band}</li>
    <li>基础 FBA 毛利：{base_profit}</li>
  </ul>
</body>
</html>"""


def render_data_workbook(package: dict, output_path: str | Path) -> None:
    sheets = _build_workbook_sheets(package)
    _write_xlsx(Path(output_path), sheets)


def build_outputs(input_path: str, output_dir: str) -> None:
    package = json.loads(Path(input_path).read_text(encoding="utf-8"))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "research_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_markdown(package), encoding="utf-8")
    (out / "summary.md").write_text(render_summary(package), encoding="utf-8")
    (out / "dashboard.html").write_text(render_dashboard(package), encoding="utf-8")
    render_data_workbook(package, out / "data.xlsx")


def _build_workbook_sheets(package: dict) -> list[tuple[str, list[list[object]]]]:
    meta = package.get("metadata", {})
    constraints = package.get("constraints", {})
    operator_inputs = package.get("operator_inputs", {})
    market = package.get("market_analysis", {})
    competitors = package.get("competitor_pool", {})
    profit = package.get("profit_reference", {})
    return_risk = package.get("return_risk", {})
    ip_screening = package.get("ip_screening", {})
    compliance = package.get("compliance_screening", {})
    status = package.get("status_card", {})

    return [
        ("数据来源说明", _source_rows(meta)),
        (
            "调研边界",
            _dict_rows(
                {
                    "站点": meta.get("site"),
                    "关键词/品类": meta.get("seed_keyword_or_category"),
                    "产品形态": meta.get("product_shape"),
                    "明确禁区": constraints.get("exclusion_rules"),
                }
            ),
        ),
        ("运营手填项", _dict_rows(operator_inputs)),
        ("市场结构", _dict_rows(market)),
        (
            "Top100原始明细",
            _table_rows(
                package.get("normalized_tables", {}).get("top100"),
                ["ASIN", "标题", "价格", "BSR", "上架时间", "来源"],
            ),
        ),
        ("竞品池", _competitor_rows(competitors)),
        ("利润测算输入", _dict_rows(operator_inputs)),
        ("利润参考结果", _dict_rows(profit)),
        ("退货风险", _dict_rows(return_risk)),
        ("知产初筛", _dict_rows(ip_screening)),
        ("合规认证预判", _dict_rows(compliance)),
        ("状态卡", _dict_rows(status)),
    ]


def _source_rows(meta: dict) -> list[list[object]]:
    rows: list[list[object]] = [["来源", "说明"]]
    for source in meta.get("data_sources", []):
        rows.append([source, "metadata.data_sources"])
    if len(rows) == 1:
        rows.append(["待填", ""])
    return rows


def _dict_rows(data: dict) -> list[list[object]]:
    rows: list[list[object]] = [["字段", "值"]]
    for key, value in data.items():
        rows.append([key, _display_value(value)])
    if len(rows) == 1:
        rows.append(["待填", ""])
    return rows


def _table_rows(data: object, headers: list[str]) -> list[list[object]]:
    rows: list[list[object]] = [headers]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append([_display_value(item.get(header)) for header in headers])
    if len(rows) == 1:
        rows.append(["待填"] + [""] * (len(headers) - 1))
    return rows


def _competitor_rows(competitors: dict) -> list[list[object]]:
    rows: list[list[object]] = [["分组", "ASIN", "标题", "价格", "BSR", "上架时间", "备注"]]
    groups = [
        ("top10", "Top10 标杆组"),
        ("recent_winners", "近半年放量新品组"),
        ("structure_supplement", "结构补充组"),
    ]
    for key, label in groups:
        for item in competitors.get(key, []):
            if isinstance(item, dict):
                rows.append(
                    [
                        label,
                        item.get("asin"),
                        item.get("title"),
                        item.get("price"),
                        item.get("bsr"),
                        item.get("listing_date"),
                        item.get("note"),
                    ]
                )
    if len(rows) == 1:
        rows.append(["待填", "", "", "", "", "", ""])
    return rows


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _write_xlsx(output_path: Path, sheets: list[tuple[str, list[list[object]]]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("docProps/core.xml", _core_props_xml())
        archive.writestr("docProps/app.xml", _app_props_xml())
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheets)))
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(rows))


def _content_types_xml(sheet_count: int) -> str:
    sheet_overrides = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {sheet_overrides}
</Types>"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _core_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:creator>amz-product-research-workbench</dc:creator>
</cp:coreProperties>"""


def _app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>amz-product-research-workbench</Application>
</Properties>"""


def _workbook_xml(sheets: list[tuple[str, list[list[object]]]]) -> str:
    sheet_nodes = "\n".join(
        f'<sheet name="{_xml_attr(_safe_sheet_name(name))}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    {sheet_nodes}
  </sheets>
</workbook>"""


def _workbook_rels_xml(sheet_count: int) -> str:
    rel_nodes = "\n".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {rel_nodes}
</Relationships>"""


def _worksheet_xml(rows: list[list[object]]) -> str:
    row_nodes = "\n".join(
        f'<row r="{row_index}">{_cells_xml(row, row_index)}</row>'
        for row_index, row in enumerate(rows, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {row_nodes}
  </sheetData>
</worksheet>"""


def _cells_xml(row: list[object], row_index: int) -> str:
    cells = []
    for column_index, value in enumerate(row, start=1):
        cell_ref = f"{_column_letter(column_index)}{row_index}"
        text = xml_escape(_display_value(value))
        cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
    return "".join(cells)


def _xml_attr(value: str) -> str:
    return xml_escape(value, {'"': "&quot;"})


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _safe_sheet_name(name: str) -> str:
    invalid_chars = set("[]:*?/\\")
    safe = "".join("_" if char in invalid_chars else char for char in name)
    return safe[:31] or "Sheet"


if __name__ == "__main__":
    raise SystemExit("Use build_outputs(input_path, output_dir) from a wrapper script.")
