"""HTML 正式报告渲染。"""

from __future__ import annotations

import re
from html import escape
from typing import Any

from packages.report_renderer.formatting import _clean_display_title, _format_generated_at, _site_currency_code
from packages.report_renderer.markdown import render_markdown


def render_report_html(package: dict[str, Any]) -> str:
    markdown = render_markdown(package)
    meta = package.get("metadata", {}) if isinstance(package, dict) else {}
    title = _clean_display_title(meta.get("seed_keyword_or_category", "AMZ 选品报告"))
    generated_at = _format_generated_at(meta.get("generated_at", ""))
    site = str(meta.get("site") or "US")
    currency_code = _site_currency_code(site)
    toc = _toc_items(markdown)
    body = _markdown_to_html(markdown)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} / 网页报告</title>
  <style>{REPORT_HTML_STYLE}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <div class="brand">AMZ 选品报告</div>
      <h1>{escape(title)}</h1>
      <div class="meta-line">
        <span>站点 {escape(site)}</span>
        <span>金额口径 {escape(currency_code)}</span>
        <span>生成时间 {escape(generated_at or "待填")}</span>
      </div>
    </div>
    <nav class="file-links" aria-label="报告文件">
      <a href="dashboard.html">摘要看板</a>
      <a href="data.xlsx">Excel 底表</a>
      <a href="report.md">Markdown</a>
    </nav>
  </header>
  <div class="shell">
    <aside class="toc" aria-label="报告目录">
      <div class="toc-title">目录</div>
      <nav>
        {''.join(f'<a href="#{escape(item["id"])}">{escape(item["label"])}</a>' for item in toc)}
      </nav>
    </aside>
    <main class="report" id="main-content">
      {body}
    </main>
  </div>
</body>
</html>"""


def _toc_items(markdown: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in markdown.splitlines():
        if not line.startswith("## "):
            continue
        label = line[3:].strip()
        anchor = _anchor_id(label, seen)
        items.append({"label": label, "id": anchor})
    return items


def _markdown_to_html(markdown: str) -> str:
    lines: list[str] = []
    in_ul = False
    in_ol = False
    seen: set[str] = set()

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            lines.append("</ul>")
            in_ul = False
        if in_ol:
            lines.append("</ol>")
            in_ol = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            close_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_lists()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 1:
                lines.append(f'<h1 class="doc-title">{_inline_html(text)}</h1>')
            else:
                anchor = _anchor_id(text, seen) if level == 2 else ""
                attr = f' id="{anchor}"' if anchor else ""
                lines.append(f"<h{level}{attr}>{_inline_html(text)}</h{level}>")
            continue

        bullet = re.match(r"^\s*-\s+(.+)$", line)
        if bullet:
            if in_ol:
                lines.append("</ol>")
                in_ol = False
            if not in_ul:
                lines.append("<ul>")
                in_ul = True
            lines.append(f"<li>{_inline_html(bullet.group(1).strip())}</li>")
            continue

        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ordered:
            if in_ul:
                lines.append("</ul>")
                in_ul = False
            if not in_ol:
                lines.append("<ol>")
                in_ol = True
            lines.append(f"<li>{_inline_html(ordered.group(1).strip())}</li>")
            continue

        close_lists()
        lines.append(f"<p>{_inline_html(line.strip())}</p>")

    close_lists()
    return "\n".join(lines)


def _anchor_id(text: str, seen: set[str]) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip()).strip("-").lower()
    slug = slug or "section"
    base = slug
    index = 2
    while slug in seen:
        slug = f"{base}-{index}"
        index += 1
    seen.add(slug)
    return slug


def _inline_html(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


REPORT_HTML_STYLE = """
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --surface-soft: #f1f5f9;
  --text: #0f172a;
  --muted: #64748b;
  --line: #dbe3ef;
  --line-strong: #cbd5e1;
  --primary: #123a67;
  --accent: #0369a1;
  --accent-soft: #dff2ff;
  --warning: #9a5b00;
  --success: #166534;
  --shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 16px;
  line-height: 1.65;
  letter-spacing: 0;
}
a { color: inherit; }

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 32px;
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(14px);
}
.brand {
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.topbar h1 {
  margin: 4px 0 6px;
  font-size: clamp(22px, 2.2vw, 34px);
  line-height: 1.2;
  letter-spacing: 0;
}
.meta-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--muted);
  font-size: 13px;
}
.meta-line span,
.file-links a {
  display: inline-flex;
  min-height: 32px;
  align-items: center;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  padding: 4px 10px;
}
.file-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  min-width: 240px;
}
.file-links a {
  color: var(--primary);
  font-weight: 700;
  text-decoration: none;
  transition: background 180ms ease, border-color 180ms ease;
}
.file-links a:focus-visible,
.toc a:focus-visible {
  outline: 3px solid rgba(3, 105, 161, 0.32);
  outline-offset: 2px;
}
.file-links a:hover {
  background: var(--accent-soft);
  border-color: #8bd3ff;
}

.shell {
  display: grid;
  grid-template-columns: 288px minmax(0, 1fr);
  gap: 28px;
  max-width: 1440px;
  margin: 0 auto;
  padding: 28px 32px 56px;
}
.toc {
  position: sticky;
  top: 122px;
  align-self: start;
  max-height: calc(100dvh - 150px);
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: var(--shadow);
  padding: 16px;
}
.toc-title {
  margin-bottom: 10px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.toc nav {
  display: grid;
  gap: 4px;
}
.toc a {
  display: block;
  border-radius: 8px;
  padding: 8px 10px;
  color: #334155;
  font-size: 14px;
  line-height: 1.35;
  text-decoration: none;
}
.toc a:hover {
  background: var(--surface-soft);
  color: var(--primary);
}

.report {
  min-width: 0;
  max-width: 980px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: var(--shadow);
  padding: clamp(22px, 4vw, 48px);
}
.doc-title {
  margin: 0 0 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
  color: var(--primary);
  font-size: clamp(30px, 4vw, 48px);
  line-height: 1.12;
  letter-spacing: 0;
}
.report h2 {
  margin: 44px 0 16px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
  color: var(--primary);
  font-size: clamp(24px, 2.4vw, 32px);
  line-height: 1.25;
  letter-spacing: 0;
}
.report h3 {
  margin: 28px 0 10px;
  color: #1e3a5f;
  font-size: 19px;
  line-height: 1.35;
  letter-spacing: 0;
}
.report p {
  margin: 10px 0;
  color: #334155;
}
.report ul,
.report ol {
  margin: 8px 0 18px;
  padding-left: 22px;
}
.report li {
  margin: 6px 0;
  color: #334155;
}
.report code {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface-soft);
  padding: 1px 5px;
  color: #0f3b63;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
}
.report strong {
  color: var(--text);
  font-weight: 800;
}

@media (max-width: 980px) {
  .topbar {
    position: static;
    align-items: flex-start;
    flex-direction: column;
    padding: 18px 18px;
  }
  .file-links {
    justify-content: flex-start;
    min-width: 0;
  }
  .shell {
    display: block;
    padding: 18px 14px 36px;
  }
  .toc {
    position: static;
    max-height: none;
    margin-bottom: 16px;
  }
  .report {
    padding: 22px 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .file-links a { transition: none; }
}
"""
