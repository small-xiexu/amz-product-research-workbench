#!/usr/bin/env python3
"""Stage 12 后置校验：检查 HTML 中的数字是否都能在 report_data.json 中找到来源。

在 fix_report_tables.py 之后运行。提取 HTML 中所有数值（金额、销量、百分比等），
逐一验证是否存在于 report_data.json 中。找不到来源的数字标记为"可疑"。

Usage:
  python3 scripts/validate_html_numbers.py <run_dir> [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 在 HTML 文本中提取数值的正则
VALUE_PATTERNS: list[tuple[str, str]] = [
    # $金额（含范围）
    (r'\$\d+(?:,\d{3})*(?:\.\d+)?(?:\s*[-–~]\s*\$?\d+(?:,\d{3})*(?:\.\d+)?)?(?:\s*[万M])?'
     r'(?:\s*/\s*(?:天|月|年|路线))?',
     "美元金额"),
    # 万/千/百万 单位数值
    (r'\d+(?:\.\d+)?\s*[万M千K]', "带单位数值"),
    # 纯数字（销量、产品数、评论数等 ≥100 的大数）
    (r'(?<![$\w])\d{1,3}(?:,\d{3})+(?:\+\s*)?(?!\s*[万M千Kpx%])', "千分位大数"),
    # 百分比
    (r'\d+(?:\.\d+)?%', "百分比"),
    # 评分
    (r'(?<=[>\s])\d\.\d(?=[<\s])', "评分"),
]

# HTML 中不应检查的 context（CSS、JS、注释）
SKIP_CONTEXTS = [
    (re.compile(r'<style[^>]*>.*?</style>', re.DOTALL), "CSS"),
    (re.compile(r'<!--.*?-->', re.DOTALL), "HTML注释"),
    (re.compile(r'<script[^>]*>.*?</script>', re.DOTALL), "JavaScript"),
]

# 可以忽略的常见数字（非数据类）
IGNORE_VALUES = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "12", "14", "16", "18", "20", "24", "30", "32", "36",
    "40", "48", "50", "60", "72",
    "100", "150", "200", "300", "500", "600",
    "0%", "5%", "10%", "20%", "25%", "30%", "40%", "50%",
    "1.0", "1.5", "2.0", "3.0", "4.0", "5.0",
    "1.5mm", "0.3mm", "1mm", "2kg", "5kg",
    "0.5mm", "75mm", "12mm", "1.8mm",
    "$5", "$3-5", "$500-1000",
}


def _is_meaningful_value(v: str) -> bool:
    """过滤空值、占位符、纯描述性文本。"""
    if not v or v.strip() == "":
        return False
    if v in ("待补", "__ai_judgment__", "N/A", "-", "null", "None"):
        return False
    # 必须包含数字或 $ 才是数据值
    return bool(re.search(r'[\d$]', v))


# 非数据字段名（元数据/标识符），其值不加入参考集
_NON_DATA_KEYS = {
    # 纯元数据 — 这些字段的值永远不会是业务数据
    "node_id", "category_path", "route_id",
    "asin", "packet_id",
    "run_id", "schema_version", "generated_at", "snapshot_date",
    "execution_mode", "provenance_note",
    "condition", "go_threshold", "nogo_threshold", "current_status",
    "exit_criteria", "if_fail",
    "data_gaps", "critical_inputs", "freshness_note",
    "source_path", "evidence_basis",
}


def _collect_report_data_values(data: Any) -> set[str]:
    """递归收集 report_data.json 中所有数值型 value。"""
    values: set[str] = set()

    def walk(obj: Any, parent_key: str = "") -> None:
        if isinstance(obj, dict):
            # 优先收集 "value" 包装字段
            raw = obj.get("value")
            if raw is not None and isinstance(raw, (str, int, float)):
                v = str(raw).strip()
                if _is_meaningful_value(v):
                    values.add(v)
                    values.add(v.replace(",", ""))
                    if v.startswith("$"):
                        values.add(v[1:])
            # 同时收集平铺的叶子值（非元数据字段）
            for k, val in obj.items():
                if k in _NON_DATA_KEYS:
                    continue
                if isinstance(val, (str, int, float)) and not isinstance(val, bool):
                    v = str(val).strip()
                    if _is_meaningful_value(v):
                        values.add(v)
                        values.add(v.replace(",", ""))
                        if v.startswith("$"):
                            values.add(v[1:])
                elif isinstance(val, (dict, list)):
                    walk(val, k)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, parent_key)

    walk(data)
    return values


def _normalize_html_value(raw: str) -> str:
    """清理 HTML 中提取的原始值。"""
    v = raw.strip()
    v = v.replace("$", "").replace(",", "").replace("+", "").replace("~", "")
    v = re.sub(r'\s+', '', v)
    return v


def _extract_html_text(html: str) -> str:
    """从 HTML 中提取纯文本（去除 style/script/注释）。"""
    text = html
    for pattern, _ in SKIP_CONTEXTS:
        text = pattern.sub(" ", text)
    # 去除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text)
    return text


_NUMERIC_TOKEN_RE = re.compile(
    r'(?<![a-zA-Z0-9])'
    r'('
    r'\d{1,3}(?:,\d{3})+(?:\.\d+)?'         # 千分位数字
    r'|\d+(?:\.\d+)?'                        # 普通数字
    r')'
    r'(?:[万KkMm]|%)?'                       # 常见单位
    r'(?=[\s<,.)，。、]|$)',
)


def _extract_numeric_tokens(text: str) -> list[str]:
    """从复合文本（如 '2.71M units'）中提取数值 token。"""
    tokens: list[str] = []
    for m in _NUMERIC_TOKEN_RE.finditer(text):
        t = m.group(0).strip()
        if t and re.search(r'\d', t):
            tokens.append(t)
    return tokens


def _build_reference_set(report_values: set[str]) -> set[str]:
    """从 report_data 的值构建归一化参考集合。"""
    ref: set[str] = set()
    for v in report_values:
        if not v:
            continue
        ref.add(v)
        # 去除 $ 和逗号的纯净数字形式
        clean = v.replace("$", "").replace(",", "").strip()
        if clean:
            ref.add(clean)
        # 从复合文本中提取数值 token（如 "2.71M units" → add "2.71M"）
        for token in _extract_numeric_tokens(clean):
            ref.add(token)
            ref.add(token.replace(",", ""))
            # token 的格式展开
            tm = re.match(r'^([\d.]+)万$', token)
            if tm:
                num = float(tm.group(1)) * 10000
                ref.add(str(int(num)))
                ref.add(f"{int(num):,}")
            elif re.match(r'^([\d.]+)[Kk]$', token):
                pass  # _parse_numeric 已能处理
            elif re.match(r'^([\d.]+)[Mm]$', token):
                pass
        # 对 "X万" 格式，生成数值形式
        m = re.match(r'^([\d.]+)万$', clean)
        if m:
            num = float(m.group(1)) * 10000
            ref.add(str(int(num)))
            ref.add(f"{int(num):,}")
        # 对纯数字（≥5位），生成万/千/百万表达
        if re.match(r'^\d{5,}$', clean):
            n = int(clean)
            wan = n / 10000
            if wan >= 0.1:
                ref.add(f"{wan:.1f}万")
                ref.add(f"{wan:.0f}万")
            k = n / 1000
            if k >= 1:
                ref.add(f"{int(k)}K")
            mil = n / 1_000_000
            if mil >= 0.01:
                ref.add(f"{mil:.1f}M")
                ref.add(f"{mil:.2f}M")
        # 对带小数的数字（如价格），也加整数版本
        if re.match(r'^\d+\.\d{2}$', clean):
            ref.add(clean.rstrip('0').rstrip('.'))
    return ref


def _parse_numeric(raw: str) -> float | None:
    """将字符串解析为数值。支持 $/逗号/万/K/M/% 等格式。无法解析返回 None。"""
    v = raw.strip()
    if not v:
        return None
    # 百分比
    if v.endswith("%"):
        try:
            return float(v[:-1])
        except ValueError:
            return None
    # 去除 $ 和逗号
    v = v.replace("$", "").replace(",", "").strip()
    # 万
    m = re.match(r'^([\d.]+)万$', v)
    if m:
        return float(m.group(1)) * 10000
    # K/k
    m = re.match(r'^([\d.]+)[Kk]$', v)
    if m:
        return float(m.group(1)) * 1000
    # M/m (但跳过纯品牌名如 "3M"，要求数字部分存在)
    m = re.match(r'^([\d.]+)[Mm]$', v)
    if m:
        return float(m.group(1)) * 1_000_000
    try:
        return float(v)
    except ValueError:
        return None


def _values_equivalent(a: str, b: str) -> bool:
    """判断两个值是否数值上等价（±2% 容差）。"""
    na = _parse_numeric(a)
    nb = _parse_numeric(b)
    if na is None or nb is None:
        return False
    if na == 0 and nb == 0:
        return True
    if na == 0 or nb == 0:
        return False
    return abs(na - nb) / max(abs(na), abs(nb)) < 0.02


def _is_trivial_number(raw: str, normalized: str) -> bool:
    """跳过非数据类数字：CSS尺寸、品牌名、短数字等。"""
    # 小整数（≤ 24）通常是列数、排名、评分维度等
    if re.match(r'^\d{1,2}$', normalized):
        return True
    # 短混合字符串（如 3M 品牌名、4K 评论缩写等），但需含字母才跳过
    if len(normalized) <= 3 and re.search(r'[A-Za-z]', normalized):
        return True
    # 纯数字 + px/mm/cm/in 等 CSS/尺寸单位
    if re.match(r'^\d+px$', raw.lower().strip()):
        return True
    return False


def validate_html_numbers(html_path: Path, report_data_path: Path) -> tuple[list[str], bool]:
    """检查 HTML 中的数值是否在 report_data 中有来源。返回 (可疑列表, 通过)。"""
    html = html_path.read_text(encoding="utf-8")
    rd = json.loads(report_data_path.read_text(encoding="utf-8"))

    report_values = _collect_report_data_values(rd)
    reference = _build_reference_set(report_values)

    text = _extract_html_text(html)

    suspicious: list[str] = []

    for pattern, label in VALUE_PATTERNS:
        for m in re.finditer(pattern, text):
            raw = m.group(0).strip()
            normalized = _normalize_html_value(raw)

            if not normalized:
                continue
            if raw in IGNORE_VALUES or normalized in IGNORE_VALUES:
                continue
            if _is_trivial_number(raw, normalized):
                continue

            # Step 1: 精确/归一化 字符串匹配
            found = False
            candidates = [
                raw, normalized,
                raw.replace(",", ""), raw.replace("$", ""),
                raw.replace("$", "").replace(",", ""),
            ]
            for c in candidates:
                if c and c in reference:
                    found = True
                    break

            # Step 2: 数值等价匹配（±2% 容差）
            if not found:
                for ref_v in reference:
                    if _values_equivalent(raw, ref_v):
                        found = True
                        break

            # Step 3: 范围匹配（"$13-36" → 分别验证 13 和 36）
            if not found:
                range_match = re.match(r'^(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)$', normalized)
                if range_match:
                    lo, hi = range_match.groups()
                    lo_ok = any(_values_equivalent(lo, r) for r in reference)
                    hi_ok = any(_values_equivalent(hi, r) for r in reference)
                    if lo_ok and hi_ok:
                        found = True

            if not found:
                ctx = _get_context(text, m.start())
                suspicious.append(f"[{label}] {raw} → 上下文: ...{ctx}...")

    return suspicious, len(suspicious) == 0


def _get_context(text: str, pos: int, window: int = 60) -> str:
    start = max(0, pos - window // 2)
    end = min(len(text), pos + window // 2)
    return text[start:end].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate HTML numbers against report_data.json")
    parser.add_argument("run_dir", type=str, help="Run directory path")
    parser.add_argument("--strict", action="store_true", help="Fail on any suspicious numbers")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    analysis = run_dir / "analysis"
    if not analysis.is_dir():
        print(f"ERROR: {analysis} 不是有效目录")
        sys.exit(1)

    rd_path = analysis / "report_data.json"
    if not rd_path.is_file():
        print(f"ERROR: 找不到 {rd_path}")
        sys.exit(1)

    html_files = sorted(analysis.glob("*分析报告*.html"))
    if not html_files:
        print("WARNING: 未找到 HTML 报告")
        sys.exit(0)

    html_path = html_files[0]
    print(f"校验: {html_path.name}")
    print(f"对照: report_data.json\n")

    suspicious, passed = validate_html_numbers(html_path, rd_path)

    if not suspicious:
        print("✅ 所有数值均能在 report_data.json 中找到来源")
        sys.exit(0)

    print(f"⚠️  发现 {len(suspicious)} 个可疑数值（未在 report_data.json 中找到来源）：\n")
    for s in suspicious[:20]:
        print(f"  {s}")

    if len(suspicious) > 20:
        print(f"  ... 及其他 {len(suspicious) - 20} 个")

    if args.strict:
        print("\n❌ strict 模式下校验失败")
        sys.exit(1)
    else:
        print(f"\n⚠️  请人工核实上述数值是否合理。严格的数值校验用 --strict。")
        sys.exit(0)


if __name__ == "__main__":
    main()
