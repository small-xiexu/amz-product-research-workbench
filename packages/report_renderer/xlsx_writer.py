"""Small XLSX writer shared by report renderers and review templates."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape as xml_escape


def write_xlsx(output_path: Path, sheets: list[tuple[str, list[list[object]]]]) -> None:
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
    column_nodes = _columns_xml(rows)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  {column_nodes}
  <sheetData>
    {row_nodes}
  </sheetData>
</worksheet>"""


def _columns_xml(rows: list[list[object]]) -> str:
    widths = _worksheet_column_widths(rows)
    if not widths:
        return ""
    nodes = "\n".join(
        f'<col min="{index}" max="{index}" width="{width:.1f}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    return f"<cols>\n    {nodes}\n  </cols>"


def _worksheet_column_widths(rows: list[list[object]]) -> list[float]:
    column_count = max((len(row) for row in rows), default=0)
    if column_count == 0:
        return []
    headers = [str(rows[0][index]).strip() if index < len(rows[0]) else "" for index in range(column_count)]
    widths: list[float] = []
    for column_index in range(column_count):
        header = headers[column_index]
        values = [row[column_index] for row in rows if column_index < len(row)]
        max_units = max((_display_width(value) for value in values), default=0)
        min_width, max_width = _column_width_bounds(header)
        width = max(min_width, min(max_units * 1.05 + 2, max_width))
        widths.append(round(width, 1))
    return widths


def _column_width_bounds(header: str) -> tuple[float, float]:
    key = header.strip().lower()
    bounds = {
        "field": (24, 32),
        "label": (16, 24),
        "value": (18, 28),
        "currency": (18, 26),
        "填写口径": (18, 30),
        "required": (12, 18),
        "是否必填": (12, 18),
        "default": (18, 32),
        "note": (52, 90),
        "说明": (36, 90),
        "标题": (36, 72),
        "商品标题": (42, 80),
        "来源": (32, 80),
        "证据": (36, 90),
        "下一步": (36, 90),
    }
    return bounds.get(key, (10, 56))


def _display_width(value: object) -> int:
    text = _display_value(value)
    if not text:
        return 0
    return max((_line_display_width(line) for line in text.splitlines()), default=0)


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _line_display_width(text: str) -> int:
    width = 0
    for char in text:
        code = ord(char)
        if (
            0x1100 <= code <= 0x11FF
            or 0x2E80 <= code <= 0xA4CF
            or 0xAC00 <= code <= 0xD7AF
            or 0xF900 <= code <= 0xFAFF
            or 0xFE10 <= code <= 0xFE6F
            or 0xFF00 <= code <= 0xFFEF
        ):
            width += 2
        else:
            width += 1
    return width


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
