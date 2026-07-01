#!/usr/bin/env python3
"""Stage 12 后置修正：自动修复 HTML 中表格的结构性问题 + CSS 版本同步。

在 Report Generation Agent 产出 HTML 后、build_report_xlsx 前运行。
只做确定性结构修正，不改内容、不增删数据。

修正项：
  0. CSS 同步 — 将 <style> 块内容替换为 report_template.css 最新版本
  1. 未包 .table-scroll 的 <table> → 自动包裹
  2. 缺 table width → 根据 class 或列数补充默认值
  3. 缺 <colgroup> → 根据 th 数量自动生成
  4. go-nogo 表缺 width → 补 1180px
  5. 长文本 .tc 单元格 — 内容 ≥20 字的 <td class="tc"> 移除 tc 类，允许换行
  6. nowrap 列宽自适应 — 检测 nowrap 单元格内容是否超出列宽，超出则自动撑开

Usage:
  python3 scripts/fix_report_tables.py <run_dir>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 已知表格的默认总宽
DEFAULT_WIDTHS: dict[str, int] = {
    "go-nogo": 1180,
}

# 按列数推算默认列宽（粗略值）
FALLBACK_COL_WIDTH = 140
LONGTEXT_TC_THRESHOLD = 20  # td.tc 内容超过此字数则移除 tc 类（最窄描述列 ~300px，中文 ~14px/字 ≈ 21字触达边界）


def _table_needs_scroll(html: str, table_pos: int) -> bool:
    """检查 <table> 前是否有未闭合的 .table-scroll div 包裹。"""
    before = html[max(0, table_pos - 300):table_pos]
    last_wrapper = before.rfind('<div class="table-scroll"')
    if last_wrapper == -1:
        return True
    between = before[last_wrapper:]
    return "</div>" in between


def _has_colgroup(table_inner: str) -> bool:
    return "<colgroup>" in table_inner


def _has_width(table_tag: str) -> bool:
    return 'style="width:' in table_tag or "style='width:" in table_tag


def _th_count(html: str, table_start: int) -> int:
    """数 <thead> 中的 <th> 数量。"""
    thead_match = re.search(r'<thead>(.*?)</thead>', html[table_start:], re.DOTALL)
    if not thead_match:
        return 0
    return len(re.findall(r'<th[\s>]', thead_match.group(1)))


def _detect_table_class(table_tag: str) -> str:
    m = re.search(r'class="([^"]*)"', table_tag)
    return m.group(1) if m else ""


def _wrap_in_scroll(table_html: str) -> str:
    return f'<div class="table-scroll">\n{table_html}\n</div>'


def _add_colgroup(table_html: str, col_count: int) -> str:
    if col_count <= 0:
        return table_html
    cols = "\n".join(
        f'      <col style="width:{FALLBACK_COL_WIDTH}px;">'
        for _ in range(col_count)
    )
    colgroup = f'    <colgroup>\n{cols}\n    </colgroup>'
    return table_html.replace("<thead>", f"{colgroup}\n    <thead>", 1)


def _add_width(table_html: str, width: int) -> str:
    return re.sub(
        r'<table\b',
        f'<table style="width:{width}px;"',
        table_html,
        count=1,
    )


def _fix_longtext_tc(html: str) -> tuple[str, int]:
    """将长文本（>80字）的 <td class="tc"> 移除 tc 类，避免 nowrap 溢出。"""
    td_pattern = re.compile(r'<td class="tc">(.*?)</td>', re.DOTALL)

    def _should_strip(match: re.Match) -> bool:
        inner = match.group(1)
        text = re.sub(r'<[^>]+>', '', inner).strip()
        return len(text) >= LONGTEXT_TC_THRESHOLD

    count = [0]

    def _replacer(match: re.Match) -> str:
        if _should_strip(match):
            count[0] += 1
            inner = match.group(1)
            return f"<td>{inner}</td>"
        return match.group(0)

    result = td_pattern.sub(_replacer, html)
    return result, count[0]


_NOWRAP_CLASSES = frozenset({"tc", "nowrap", "asin-cell", "keyword-cell", "brand-list-cell", "brand-cell"})
_CJK_RE = re.compile(r"[一-鿿　-〿＀-￯㐀-䶿\U00020000-\U0002a6df]")
_ASCII_RE = re.compile(r"[ -~]")
_TD_PADDING = 28
_TAG_PADDING = 24
_PILL_PADDING = 20
_CJK_PX = 15
_ASCII_PX = 8.5


def _estimate_text_px(text: str) -> float:
    """估算文本像素宽度。"""
    cjk = len(_CJK_RE.findall(text))
    ascii_chars = len(_ASCII_RE.findall(text))
    other = len(text) - cjk - ascii_chars
    return cjk * _CJK_PX + ascii_chars * _ASCII_PX + other * _CJK_PX


def _has_nowrap_class(td_attrs: str) -> bool:
    """检查 td 是否有 nowrap 相关的类。"""
    m = re.search(r'class="([^"]*)"', td_attrs)
    if not m:
        return False
    classes = set(m.group(1).split())
    return bool(classes & _NOWRAP_CLASSES)


def _auto_fit_nowrap_columns(html: str) -> tuple[str, int]:
    """检测 nowrap 单元格内容是否超出列宽，超出则自动撑开列宽。

    只扩大不缩小。增加的宽度从同表最宽的文本列中扣减，不够则加到表总宽。
    """
    table_pat = re.compile(r"<table\b[^>]*>(?:(?!</table>).)*</table>", re.DOTALL)
    fixed_count = 0

    def _fix_one_table(match: re.Match) -> str:
        nonlocal fixed_count
        table_html = match.group(0)

        # 解析 colgroup 列宽
        cg_match = re.search(r"<colgroup>(.*?)</colgroup>", table_html, re.DOTALL)
        if not cg_match:
            return table_html
        col_widths: list[int] = []
        for cm in re.finditer(r'width:\s*(\d+)px', cg_match.group(1)):
            col_widths.append(int(cm.group(1)))
        if not col_widths:
            return table_html

        n_cols = len(col_widths)

        # 计算每列 nowrap 内容所需最小宽度
        max_needed = [0.0] * n_cols
        row_pat = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
        for row_m in row_pat.finditer(table_html):
            tds = re.findall(r"<td([^>]*)>(.*?)</td>", row_m.group(1), re.DOTALL)
            for col_idx, (attrs, inner) in enumerate(tds):
                if col_idx >= n_cols:
                    break
                if not _has_nowrap_class(attrs):
                    continue
                # 提取可见文本
                text = re.sub(r"<[^>]+>", "", inner).strip()
                if not text:
                    continue
                px = _estimate_text_px(text)
                # 检查内部是否有 tag/pill（额外 padding）
                if re.search(r'class="(?:tag|pill)', inner):
                    px += _TAG_PADDING
                px += _TD_PADDING
                if px > max_needed[col_idx]:
                    max_needed[col_idx] = px

        # 计算短差
        shortfalls = [(i, int(max_needed[i] - col_widths[i] + 0.5))
                      for i in range(n_cols) if max_needed[i] > col_widths[i] + 2]
        if not shortfalls:
            return table_html

        # 扩宽列：优先从无 nowrap 的最宽文本列中扣，不够则加总宽
        new_widths = list(col_widths)
        total_extra = 0
        for col_idx, shortfall in shortfalls:
            new_widths[col_idx] += shortfall
            total_extra += shortfall

        # 尝试从最宽的文本列（无 nowrap、非路线/品牌列）回收空间
        text_cols = sorted(
            [(i, col_widths[i]) for i in range(n_cols)
             if max_needed[i] < 0.5 and col_widths[i] >= 200],
            key=lambda x: -x[1]
        )
        remaining = total_extra
        for col_idx, w in text_cols:
            if remaining <= 0:
                break
            steal = min(remaining, w - 180)
            if steal > 0:
                new_widths[col_idx] -= steal
                remaining -= steal

        # 剩余加到表总宽
        old_total = sum(col_widths)
        new_total = max(old_total, sum(new_widths))

        # 重建 colgroup
        new_cols = "\n".join(
            f'      <col style="width:{new_widths[i]}px;">'
            for i in range(n_cols)
        )
        new_cg = f"    <colgroup>\n{new_cols}\n    </colgroup>"
        new_table = table_html.replace(cg_match.group(0), new_cg, 1)

        # 更新 table width
        new_table = re.sub(
            r'(<table\b[^>]*?style=")width:\d+px',
            f'\\1width:{new_total}px',
            new_table,
            count=1,
        )

        if new_table != table_html:
            diffs = [f"col{i}({col_widths[i]}→{new_widths[i]})"
                     for i in range(n_cols) if new_widths[i] != col_widths[i]]
            fixed_count += 1
            # log is not accessible here; we'll report in the caller
        return new_table

    result = table_pat.sub(_fix_one_table, html)
    return result, fixed_count


def _load_canonical_css() -> str:
    """读取 report_template.css 最新版本。"""
    css_path = ROOT / "skills" / "amazon-product-research" / "references" / "report_template.css"
    if not css_path.is_file():
        return ""
    return css_path.read_text(encoding="utf-8").strip()


def sync_css(html: str) -> tuple[str, bool]:
    """将 HTML 中 <style> 块替换为 report_template.css 最新版本。"""
    canonical = _load_canonical_css()
    if not canonical:
        return html, False

    style_pattern = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL)
    match = style_pattern.search(html)
    if not match:
        return html, False

    existing = match.group(1).strip()
    if existing == canonical:
        return html, False

    result = html[: match.start(1)] + "\n" + canonical + "\n" + html[match.end(1):]
    return result, True


def fix_html(html: str) -> tuple[str, list[str]]:
    """修正 HTML 中的表格结构问题。返回 (修正后HTML, 修正日志)。"""
    log: list[str] = []
    result = html

    # 从后往前处理，避免替换后位置偏移
    table_pattern = re.compile(r'<table\b[^>]*>(?:(?!</table>).)*</table>', re.DOTALL)
    matches = list(table_pattern.finditer(result))

    # 倒序处理
    for m in reversed(matches):
        table_html = m.group(0)
        table_tag = re.match(r'<table\b[^>]*>', table_html).group(0)
        table_class = _detect_table_class(table_tag)
        pos = m.start()
        needs_scroll = _table_needs_scroll(result, pos)
        needs_width = not _has_width(table_tag)
        needs_colgroup = not _has_colgroup(table_html)
        col_count = _th_count(result, pos)

        if not (needs_scroll or needs_width or needs_colgroup):
            continue

        fixed = table_html
        fixes: list[str] = []

        if needs_width:
            w = DEFAULT_WIDTHS.get(table_class, col_count * FALLBACK_COL_WIDTH)
            fixed = _add_width(fixed, w)
            fixes.append(f"width={w}px")

        if needs_colgroup and col_count > 0:
            fixed = _add_colgroup(fixed, col_count)
            fixes.append(f"colgroup({col_count}cols)")

        if needs_scroll:
            fixed = _wrap_in_scroll(fixed)
            fixes.append(".table-scroll")

        result = result[:pos] + fixed + result[m.end():]
        log.append(
            f"[{table_class or 'table'}] {', '.join(fixes)} "
            f"(was: scroll={'N' if needs_scroll else 'Y'} "
            f"width={'N' if needs_width else 'Y'} "
            f"colgroup={'N' if needs_colgroup else 'Y'})"
        )

    result, tc_count = _fix_longtext_tc(result)
    if tc_count > 0:
        log.append(f"[tc-longtext] {tc_count} 个长文本 .tc 单元格已移除 tc 类")

    result, fit_count = _auto_fit_nowrap_columns(result)
    if fit_count > 0:
        log.append(f"[auto-fit] {fit_count} 个表格的 nowrap 列宽已自适应撑开")

    return result, log


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix HTML table structure issues")
    parser.add_argument("run_dir", type=str, help="Run directory path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"ERROR: {run_dir} 不是有效目录")
        sys.exit(1)

    # 找 HTML 文件
    analysis_dir = run_dir / "analysis"
    html_files = sorted(analysis_dir.glob("*分析报告*.html")) if analysis_dir.is_dir() else []
    if not html_files:
        print(f"WARNING: 在 {analysis_dir} 中未找到 HTML 报告，跳过")
        sys.exit(0)

    html_path = html_files[0]
    print(f"修正: {html_path}")

    original = html_path.read_text(encoding="utf-8")

    # Step 0: CSS 同步
    synced, css_changed = sync_css(original)
    if css_changed:
        print("  ✓ CSS 已同步为 report_template.css 最新版本")
    fixed, log = fix_html(synced)

    if not log and not css_changed:
        print("  所有表格与 CSS 已符合规范，无需修正")
        sys.exit(0)

    for entry in log:
        print(f"  ✓ {entry}")

    html_path.write_text(fixed, encoding="utf-8")
    print(f"  已写入修正后的 HTML ({len(log)} 处修正)")


if __name__ == "__main__":
    main()
