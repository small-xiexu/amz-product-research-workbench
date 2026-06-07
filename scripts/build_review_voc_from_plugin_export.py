#!/usr/bin/env python3
"""Build VOC outputs from the local Amazon review plugin exports."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from openpyxl import load_workbook
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("openpyxl is required to read review plugin Excel exports") from exc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.render_report import _write_xlsx


EXPECTED_SHEET = "评论数据"
HEADER_ALIASES = {
    "ASIN": "asin",
    "站点": "site",
    "评论ID": "review_id",
    "评论地区": "review_region",
    "原始评论日期": "raw_date",
    "评论日期": "review_date",
    "原始评星": "raw_rating",
    "评星": "rating",
    "情绪": "sentiment",
    "评论人": "author",
    "评论人主页": "author_profile_url",
    "是否验证购买": "verified",
    "Helpful数量": "helpful_count",
    "是否有买家实拍": "has_buyer_image",
    "图片数量": "image_count",
    "图片链接": "image_urls",
    "是否有视频": "has_video",
    "评论产品的属性": "variant",
    "颜色": "color",
    "尺寸": "size",
    "英文标题": "title_en",
    "英文评论": "body_en",
    "标题中文翻译": "title_zh",
    "评论中文翻译": "body_zh",
    "评论链接": "url",
}

PAIN_RULES = [
    {
        "name": "耐用/断裂问题",
        "keywords": ["断", "坏", "裂", "撕裂", "脱线", "不耐用", "失效", "broke", "broken", "break", "last", "ripped", "tear"],
        "suggestion": "优先复核受力件、连接件、缝线、扣具或核心材料的耐久方案。",
    },
    {
        "name": "安全/失控风险",
        "keywords": ["安全", "危险", "挣脱", "跑掉", "失控", "扣", "夹", "danger", "unsafe", "escape", "clip", "buckle"],
        "suggestion": "进入深挖时把安全和责任风险前置，必要时要求供应商提供测试或加固方案。",
    },
    {
        "name": "尺寸/适配不清",
        "keywords": ["太小", "太大", "尺寸", "尺码", "腰围", "适配", "small", "large", "fit", "loose", "tight"],
        "suggestion": "优化尺码分层、适配范围和页面说明，降低误购和退货。",
    },
    {
        "name": "收纳/配件体验不足",
        "keywords": ["袋", "收纳", "手机", "钥匙", "拉链", "pouch", "bag", "pocket", "zipper", "phone"],
        "suggestion": "把配件从附赠感改成可用性设计，明确容量边界。",
    },
    {
        "name": "舒适/噪音/使用体验",
        "keywords": ["不舒服", "疼", "噪音", "晃", "滑", "硬", "comfortable", "noise", "jingle", "stiff", "slip"],
        "suggestion": "复核长时间使用场景下的佩戴、握持、静音和柔韧性。",
    },
    {
        "name": "预期不符/质量落差",
        "keywords": ["失望", "浪费", "不值", "退货", "差", "cheap", "waste", "return", "disappointed", "poor quality"],
        "suggestion": "检查 Listing 承诺是否过强，并用更真实的参数、场景和边界降低预期落差。",
    },
]

HIGHLIGHT_RULES = [
    {
        "name": "解放双手/使用便利",
        "keywords": ["免提", "解放双手", "hands free", "free hands", "convenient", "easy"],
    },
    {
        "name": "缓冲/控制感",
        "keywords": ["缓冲", "弹力", "控制", "手柄", "bungee", "shock", "control", "handle"],
    },
    {
        "name": "结实/质量好",
        "keywords": ["结实", "耐用", "质量好", "sturdy", "durable", "quality", "strong"],
    },
    {
        "name": "价格/性价比",
        "keywords": ["价格", "性价比", "值得", "value", "price", "worth"],
    },
    {
        "name": "收纳/场景加分",
        "keywords": ["收纳", "袋", "手机", "钥匙", "pouch", "bag", "pocket", "phone"],
    },
]


class MarkdownBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_style_or_script = False
        self.markdown_depth = 0
        self.chips: list[str] = []
        self.body_parts: list[str] = []
        self._capture_chip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if tag in {"style", "script"}:
            self.in_style_or_script = True
        if tag == "div" and "markdown-body" in class_name:
            self.markdown_depth += 1
        elif self.markdown_depth and tag in {"p", "h1", "h2", "h3", "h4", "li"}:
            self.body_parts.append("\n")
        if tag == "span" and self._inside_chips(attrs_dict, class_name):
            self._capture_chip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script"}:
            self.in_style_or_script = False
        if tag == "div" and self.markdown_depth:
            self.markdown_depth -= 1
        if tag == "span":
            self._capture_chip = False

    def handle_data(self, data: str) -> None:
        text = compact_text(data)
        if not text or self.in_style_or_script:
            return
        if self._capture_chip:
            self.chips.append(text)
        if self.markdown_depth:
            self.body_parts.append(text)

    @staticmethod
    def _inside_chips(attrs: dict[str, str], class_name: str) -> bool:
        return "chips" in attrs.get("data-parent-class", "") or "chip" in class_name or True


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_date(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return compact_text(value)


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ".").strip())
    except ValueError:
        return None


def to_int(value: Any) -> int:
    number = to_float(value)
    return int(number) if number is not None else 0


def read_review_excel(path: Path) -> list[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet_name = EXPECTED_SHEET if EXPECTED_SHEET in workbook.sheetnames else workbook.sheetnames[0]
    worksheet = workbook[sheet_name]
    rows = worksheet.iter_rows(values_only=True)
    try:
        header_values = next(rows)
    except StopIteration:
        return []
    headers = [HEADER_ALIASES.get(compact_text(value), compact_text(value)) for value in header_values]
    records: list[dict[str, Any]] = []
    for row in rows:
        if not any(value not in (None, "") for value in row):
            continue
        raw = {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
        record = normalize_review(raw, path)
        if record.get("review_id") or record.get("review_text") or record.get("review_text_zh"):
            records.append(record)
    return records


def normalize_review(raw: dict[str, Any], source_path: Path) -> dict[str, Any]:
    rating = to_float(raw.get("rating"))
    title_en = compact_text(raw.get("title_en"))
    body_en = compact_text(raw.get("body_en"))
    title_zh = compact_text(raw.get("title_zh"))
    body_zh = compact_text(raw.get("body_zh"))
    review_text = compact_text(" ".join(part for part in [title_en, body_en] if part))
    review_text_zh = compact_text(" ".join(part for part in [title_zh, body_zh] if part))
    review_id = compact_text(raw.get("review_id")) or fallback_review_id(raw)
    return {
        "review_id": review_id,
        "asin": compact_text(raw.get("asin")),
        "site": compact_text(raw.get("site")),
        "review_region": compact_text(raw.get("review_region")),
        "raw_date": compact_text(raw.get("raw_date")),
        "review_date": clean_date(raw.get("review_date")),
        "raw_rating": compact_text(raw.get("raw_rating")),
        "rating": rating if rating is not None else compact_text(raw.get("rating")),
        "sentiment": compact_text(raw.get("sentiment")) or infer_sentiment(rating),
        "author": compact_text(raw.get("author")),
        "verified": compact_text(raw.get("verified")),
        "helpful_count": to_int(raw.get("helpful_count")),
        "has_buyer_image": compact_text(raw.get("has_buyer_image")),
        "image_count": to_int(raw.get("image_count")),
        "image_urls": compact_text(raw.get("image_urls")),
        "has_video": compact_text(raw.get("has_video")),
        "variant": compact_text(raw.get("variant")),
        "color": compact_text(raw.get("color")),
        "size": compact_text(raw.get("size")),
        "review_text": review_text,
        "review_text_zh": review_text_zh,
        "url": compact_text(raw.get("url")),
        "source_file": source_path.name,
    }


def fallback_review_id(raw: dict[str, Any]) -> str:
    source = "|".join(compact_text(raw.get(key)) for key in ("asin", "review_date", "author", "body_en", "body_zh"))
    return "review-" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


def infer_sentiment(rating: float | None) -> str:
    if rating is None:
        return ""
    if rating >= 4:
        return "正面"
    if rating == 3:
        return "中性"
    if rating > 0:
        return "负面"
    return ""


def read_ai_report(path: Path) -> dict[str, Any]:
    parser = MarkdownBodyParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    text = "\n".join(part for part in parser.body_parts if compact_text(part))
    return {
        "source_file": path.name,
        "chips": parser.chips,
        "text": compact_text(text),
    }


def build_voc_package(
    reviews: list[dict[str, Any]],
    ai_reports: list[dict[str, Any]],
    source_files: list[Path],
    candidate_id: str,
    candidate_name: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    pain_points = build_findings(reviews, PAIN_RULES, mode="pain")
    highlights = build_findings(reviews, HIGHLIGHT_RULES, mode="highlight")
    return {
        "metadata": {
            "package_id": "review-voc-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "generated_at": now,
            "source_type": "review_plugin_export",
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "source_files": [str(path) for path in source_files],
            "integration_note": "Excel is the structured source of truth; HTML AI reports are auxiliary reading references.",
        },
        "summary": build_summary(reviews),
        "pain_points": pain_points,
        "highlights": highlights,
        "opportunity_hypotheses": build_opportunity_hypotheses(pain_points),
        "ai_report_reference": {
            "source_files": [report["source_file"] for report in ai_reports],
            "text_excerpt": "\n\n".join(report["text"][:1800] for report in ai_reports if report.get("text")),
            "usage": "仅作辅助阅读，不作为可追溯证据主来源。",
        },
        "normalized_reviews": reviews,
    }


def build_summary(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    ratings = Counter(rating_bucket(review.get("rating")) for review in reviews)
    sentiments = Counter(compact_text(review.get("sentiment")) or "未识别" for review in reviews)
    asins = sorted({review.get("asin") for review in reviews if review.get("asin")})
    sites = sorted({review.get("site") for review in reviews if review.get("site")})
    dates = sorted(review.get("review_date") for review in reviews if review.get("review_date"))
    return {
        "review_count": len(reviews),
        "asin_count": len(asins),
        "site_count": len(sites),
        "asins": asins,
        "sites": sites,
        "date_range": {
            "start": dates[0] if dates else "",
            "end": dates[-1] if dates else "",
        },
        "rating_distribution": dict(sorted(ratings.items())),
        "sentiment_distribution": dict(sentiments),
        "low_rating_count": sum(1 for review in reviews if is_low_rating(review)),
        "media_review_count": sum(1 for review in reviews if has_media(review)),
    }


def rating_bucket(value: Any) -> str:
    rating = to_float(value)
    if rating is None:
        return "未识别"
    return f"{int(round(rating))}星"


def is_low_rating(review: dict[str, Any]) -> bool:
    rating = to_float(review.get("rating"))
    return rating is not None and rating <= 3


def is_positive_rating(review: dict[str, Any]) -> bool:
    rating = to_float(review.get("rating"))
    return rating is not None and rating >= 4


def has_media(review: dict[str, Any]) -> bool:
    return review.get("has_buyer_image") == "是" or review.get("has_video") == "是" or to_int(review.get("image_count")) > 0


def build_findings(reviews: list[dict[str, Any]], rules: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    eligible = [review for review in reviews if is_low_rating(review)] if mode == "pain" else [review for review in reviews if is_positive_rating(review)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmatched: list[dict[str, Any]] = []
    for review in eligible:
        matched = False
        text = searchable_text(review)
        for rule in rules:
            if any(keyword.lower() in text for keyword in rule["keywords"]):
                grouped[rule["name"]].append(review)
                matched = True
        if not matched and mode == "pain":
            unmatched.append(review)

    if unmatched:
        grouped["其他负面反馈"].extend(unmatched)

    findings = []
    for name, items in grouped.items():
        items = sorted(items, key=lambda item: (to_float(item.get("rating")) or 0, -to_int(item.get("helpful_count"))))
        findings.append(
            {
                "name": name,
                "review_count": len(items),
                "severity": severity_for(items, mode),
                "evidence": [evidence_item(item) for item in items[:10]],
            }
        )
    return sorted(findings, key=lambda item: item["review_count"], reverse=True)


def searchable_text(review: dict[str, Any]) -> str:
    return " ".join(
        [
            compact_text(review.get("review_text")),
            compact_text(review.get("review_text_zh")),
            compact_text(review.get("variant")),
            compact_text(review.get("sentiment")),
        ]
    ).lower()


def severity_for(reviews: list[dict[str, Any]], mode: str) -> str:
    if mode == "highlight":
        return "正面信号"
    count = len(reviews)
    has_one_star = any((to_float(review.get("rating")) or 0) <= 1 for review in reviews)
    if count >= 5 or has_one_star:
        return "高"
    if count >= 2:
        return "中"
    return "低"


def evidence_item(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": review.get("review_id"),
        "asin": review.get("asin"),
        "site": review.get("site"),
        "rating": review.get("rating"),
        "review_date": review.get("review_date"),
        "snippet": snippet_for(review),
        "url": review.get("url"),
    }


def snippet_for(review: dict[str, Any], limit: int = 180) -> str:
    text = compact_text(review.get("review_text_zh")) or compact_text(review.get("review_text"))
    return text[:limit] + ("..." if len(text) > limit else "")


def build_opportunity_hypotheses(pain_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions = {rule["name"]: rule["suggestion"] for rule in PAIN_RULES}
    hypotheses = []
    for point in pain_points[:8]:
        name = point["name"]
        evidence_ids = [item["review_id"] for item in point.get("evidence", []) if item.get("review_id")]
        hypotheses.append(
            {
                "name": name,
                "hypothesis": suggestions.get(name, "进入深挖时结合证据评论继续归因，判断是否为可改品机会。"),
                "evidence_review_ids": evidence_ids,
                "confidence": "中" if point.get("review_count", 0) >= 3 else "低",
            }
        )
    return hypotheses


def render_markdown(package: dict[str, Any]) -> str:
    meta = package.get("metadata", {})
    summary = package.get("summary", {})
    lines = [
        f"# {meta.get('candidate_name') or '评论 VOC'} 分析报告",
        "",
        "## 数据概况",
        f"- 评论数：{summary.get('review_count', 0)}",
        f"- ASIN 数：{summary.get('asin_count', 0)}",
        f"- 站点数：{summary.get('site_count', 0)}",
        f"- 时间范围：{summary.get('date_range', {}).get('start', '')} 至 {summary.get('date_range', {}).get('end', '')}",
        f"- 低分评论数：{summary.get('low_rating_count', 0)}",
        f"- 含图片/视频评论数：{summary.get('media_review_count', 0)}",
        "",
        "## 主要痛点",
    ]
    for point in package.get("pain_points", []):
        lines.extend([f"### {point['name']}", f"- 评论数：{point['review_count']}，风险等级：{point['severity']}"])
        for item in point.get("evidence", [])[:5]:
            lines.append(f"- `{item.get('review_id')}` / {item.get('asin')} / {item.get('rating')}星：{item.get('snippet')}")
        lines.append("")

    lines.append("## 主要亮点")
    for point in package.get("highlights", []):
        lines.extend([f"### {point['name']}", f"- 评论数：{point['review_count']}"])
        for item in point.get("evidence", [])[:5]:
            lines.append(f"- `{item.get('review_id')}` / {item.get('asin')} / {item.get('rating')}星：{item.get('snippet')}")
        lines.append("")

    lines.append("## 改品机会假设")
    for item in package.get("opportunity_hypotheses", []):
        lines.append(f"- {item['name']}：{item['hypothesis']}（证据评论：{', '.join(item.get('evidence_review_ids', [])[:5])}）")

    lines.extend(
        [
            "",
            "## 使用边界",
            "- Excel 评论数据是结构化主来源。",
            "- HTML AI 报告只作辅助阅读，正式结论必须能追溯到评论 ID。",
            "- 当前标签是规则初筛，后续可再叠加 LLM 做更细的主题聚类。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_summary(package: dict[str, Any]) -> str:
    summary = package.get("summary", {})
    pain = package.get("pain_points", [])
    highlights = package.get("highlights", [])
    return "\n".join(
        [
            "# 评论 VOC 摘要",
            "",
            f"- 评论数：{summary.get('review_count', 0)}",
            f"- 低分评论数：{summary.get('low_rating_count', 0)}",
            f"- 第一痛点：{pain[0]['name'] if pain else '待补'}",
            f"- 第一亮点：{highlights[0]['name'] if highlights else '待补'}",
            "- 下一步：把 VOC 结论合并到重点候选深挖报告，并与卖家精灵竞品池对齐 ASIN。",
        ]
    ) + "\n"


def render_workbook(package: dict[str, Any], output_path: Path) -> None:
    _write_xlsx(
        output_path,
        [
            ("数据概况", summary_rows(package)),
            ("痛点证据", finding_rows(package.get("pain_points", []))),
            ("亮点证据", finding_rows(package.get("highlights", []))),
            ("改品机会", opportunity_rows(package.get("opportunity_hypotheses", []))),
            ("评论明细", review_rows(package.get("normalized_reviews", []))),
            ("AI报告参考", ai_report_rows(package.get("ai_report_reference", {}))),
        ],
    )


def summary_rows(package: dict[str, Any]) -> list[list[Any]]:
    rows = [["字段", "值"]]
    summary = package.get("summary", {})
    for key, value in summary.items():
        rows.append([key, display_value(value)])
    return rows


def finding_rows(findings: list[dict[str, Any]]) -> list[list[Any]]:
    rows = [["主题", "评论数", "等级", "评论ID", "ASIN", "站点", "评分", "日期", "证据片段", "链接"]]
    for finding in findings:
        for item in finding.get("evidence", []):
            rows.append(
                [
                    finding.get("name"),
                    finding.get("review_count"),
                    finding.get("severity"),
                    item.get("review_id"),
                    item.get("asin"),
                    item.get("site"),
                    item.get("rating"),
                    item.get("review_date"),
                    item.get("snippet"),
                    item.get("url"),
                ]
            )
    if len(rows) == 1:
        rows.append(["待补", "", "", "", "", "", "", "", "", ""])
    return rows


def opportunity_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    rows = [["机会点", "假设", "证据评论ID", "置信度"]]
    for item in items:
        rows.append([item.get("name"), item.get("hypothesis"), "\n".join(item.get("evidence_review_ids", [])), item.get("confidence")])
    if len(rows) == 1:
        rows.append(["待补", "", "", ""])
    return rows


def review_rows(reviews: list[dict[str, Any]]) -> list[list[Any]]:
    rows = [["评论ID", "ASIN", "站点", "评分", "情绪", "日期", "Helpful", "属性", "中文评论", "英文评论", "链接"]]
    for review in reviews:
        rows.append(
            [
                review.get("review_id"),
                review.get("asin"),
                review.get("site"),
                review.get("rating"),
                review.get("sentiment"),
                review.get("review_date"),
                review.get("helpful_count"),
                review.get("variant"),
                review.get("review_text_zh"),
                review.get("review_text"),
                review.get("url"),
            ]
        )
    return rows


def ai_report_rows(reference: dict[str, Any]) -> list[list[Any]]:
    return [
        ["字段", "值"],
        ["来源文件", "\n".join(reference.get("source_files", []))],
        ["用途", reference.get("usage", "")],
        ["文本摘录", reference.get("text_excerpt", "")],
    ]


def display_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build VOC package from Amazon review plugin Excel/HTML exports.")
    parser.add_argument("output_dir", help="Directory to write review_voc_package.json and report outputs.")
    parser.add_argument("inputs", nargs="+", help="Review plugin .xlsx exports and optional .html AI reports.")
    parser.add_argument("--candidate-id", default="", help="Candidate id from candidate_pool, if available.")
    parser.add_argument("--candidate-name", default="", help="Candidate name, if available.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_paths = [Path(item).expanduser().resolve() for item in args.inputs]
    excel_paths = [path for path in input_paths if path.suffix.lower() == ".xlsx"]
    html_paths = [path for path in input_paths if path.suffix.lower() in {".html", ".htm"}]
    if not excel_paths:
        raise SystemExit("At least one review plugin Excel export is required.")

    reviews: list[dict[str, Any]] = []
    for path in excel_paths:
        reviews.extend(read_review_excel(path))
    ai_reports = [read_ai_report(path) for path in html_paths]
    package = build_voc_package(reviews, ai_reports, input_paths, args.candidate_id, args.candidate_name)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "review_voc_package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "voc_report.md").write_text(render_markdown(package), encoding="utf-8")
    (output_dir / "voc_summary.md").write_text(render_summary(package), encoding="utf-8")
    render_workbook(package, output_dir / "voc_evidence.xlsx")
    print(f"Wrote review VOC package: {output_dir / 'review_voc_package.json'}")
    print(f"Reviews: {len(reviews)}")
    print(f"Pain points: {len(package['pain_points'])}")
    print(f"Highlights: {len(package['highlights'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
