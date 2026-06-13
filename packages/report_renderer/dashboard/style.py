"""HTML 看板 CSS 样式常量（从 render_report.py R1 抽离，纯移动不改内容）。"""

DASHBOARD_STYLE = """
:root {
  --bg: #f3f0ea;
  --panel: #fffefa;
  --panel-soft: #f7f3eb;
  --panel-dark: #eef4f2;
  --panel-darker: #e5eeeb;
  --text: #1f2933;
  --muted: #6e7480;
  --line: rgba(32, 40, 51, 0.10);
  --line-soft: rgba(32, 40, 51, 0.06);
  --accent: #c57445;
  --accent-soft: #e7a56f;
  --accent-2: #52727b;
  --accent-3: #66764f;
  --shadow: 0 18px 44px rgba(28, 37, 49, 0.07);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background:
    radial-gradient(circle at top left, rgba(197, 116, 69, 0.10), transparent 34rem),
    linear-gradient(180deg, #f6f1e9 0%, #f8f5ef 100%);
  color: var(--text);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, sans-serif;
  letter-spacing: 0;
}
a { color: inherit; text-decoration: none; }
.page {
  max-width: 1540px;
  margin: 0 auto;
  padding: 24px 24px 44px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.16fr) minmax(360px, 0.84fr);
  gap: 16px;
  align-items: stretch;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 26px;
}
.panel-dark {
  background: linear-gradient(160deg, var(--panel-dark) 0%, var(--panel-darker) 100%);
  border: 1px solid rgba(32, 40, 51, 0.08);
  color: var(--text);
}
.eyebrow {
  font-size: 12px;
  line-height: 1;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #c47a4d;
  font-weight: 700;
}
.title {
  margin: 10px 0 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.title-en {
  font-size: 46px;
  line-height: 1.04;
  letter-spacing: 0;
}
.title-cn {
  font-size: 18px;
  line-height: 1.25;
  color: var(--muted);
  font-weight: 600;
  letter-spacing: 0;
}
.subtitle {
  max-width: 60ch;
  font-size: 15px;
  line-height: 1.8;
  color: var(--muted);
}
.badge-row,
.pill-row,
.link-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.badge,
.pill,
.link-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  border: 1px solid rgba(32, 40, 51, 0.08);
  background: rgba(32, 40, 51, 0.04);
  color: var(--text);
}
.badge.dark,
.pill.dark {
  border-color: rgba(32, 40, 51, 0.08);
  background: rgba(255, 255, 255, 0.72);
  color: var(--text);
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}
.hero-meta .badge {
  font-weight: 600;
}
.hero-status {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.status-label {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(32, 40, 51, 0.58);
  font-weight: 700;
}
.status-value {
  margin: 12px 0 10px;
  font-size: 42px;
  line-height: 1;
  font-weight: 800;
  color: var(--text);
}
.status-copy {
  font-size: 15px;
  line-height: 1.75;
  color: var(--muted);
  max-width: 42ch;
}
.status-note {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(32, 40, 51, 0.08);
  font-size: 13px;
  line-height: 1.65;
  color: var(--text);
}
.status-stack {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}
.status-bullet {
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(32, 40, 51, 0.08);
  font-size: 13px;
  line-height: 1.55;
  color: var(--text);
  overflow-wrap: anywhere;
}
.summary-strip {
  margin-top: 22px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.summary-item {
  min-height: 112px;
  padding: 14px;
  border-radius: 8px;
  background: var(--panel-soft);
  border: 1px solid var(--line-soft);
}
.summary-label {
  font-size: 12px;
  line-height: 1;
  color: var(--muted);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.summary-value {
  margin-top: 9px;
  font-size: 20px;
  line-height: 1.35;
  font-weight: 850;
  overflow-wrap: anywhere;
}
.summary-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
}
.metric-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.metric-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 18px;
  min-height: 128px;
}
.metric-label {
  font-size: 12px;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--muted);
}
.metric-value {
  margin-top: 10px;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 800;
}
.metric-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--muted);
}
.section {
  margin-top: 30px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 22px;
}
.section-title {
  margin: 0;
  font-size: 25px;
  line-height: 1.2;
  letter-spacing: 0;
  max-width: 24ch;
}
.section-note {
  max-width: 64ch;
  font-size: 13px;
  line-height: 1.65;
  color: var(--muted);
}
.two-col {
  display: grid;
  grid-template-columns: 1.08fr 0.92fr;
  gap: 18px;
}
.stack {
  display: grid;
  gap: 18px;
}
.subpanel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
  padding: 24px;
}
.subpanel.dark {
  background: linear-gradient(160deg, #f0f4f8 0%, #e6edf3 100%);
  border: 1px solid rgba(32, 40, 51, 0.08);
  color: var(--text);
}
.bar-group {
  display: grid;
  gap: 14px;
}
.bar-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}
.bar-label {
  font-size: 13px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
.bar-track {
  position: relative;
  height: 11px;
  border-radius: 999px;
  background: rgba(32, 40, 51, 0.08);
  overflow: hidden;
}
.bar-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--accent-soft));
}
.bar-fill.alt {
  background: linear-gradient(90deg, var(--accent-2), #8da98a);
}
.bar-fill.cool {
  background: linear-gradient(90deg, #8793a7, #e0a461);
}
.bar-value {
  font-size: 13px;
  color: var(--muted);
  white-space: nowrap;
}
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.info-card {
  padding: 14px;
  border-radius: 8px;
  background: var(--panel-soft);
  border: 1px solid var(--line-soft);
}
.info-card.dark {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(32, 40, 51, 0.08);
}
.info-label {
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.info-card.dark .info-label {
  color: rgba(32, 40, 51, 0.58);
}
.info-value {
  margin-top: 8px;
  font-size: 23px;
  line-height: 1.2;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.info-note {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.info-card.dark .info-note {
  color: var(--muted);
}
.note-list {
  display: grid;
  gap: 10px;
}
.note-item {
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(32, 40, 51, 0.04);
  border: 1px solid rgba(32, 40, 51, 0.07);
  font-size: 13px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.note-item.dark {
  background: rgba(255, 255, 255, 0.82);
  border-color: rgba(32, 40, 51, 0.08);
  color: var(--text);
}
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.table th,
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(32, 40, 51, 0.08);
  text-align: left;
  vertical-align: top;
}
.table th {
  color: var(--muted);
  font-weight: 700;
  white-space: nowrap;
}
.table tr:last-child td { border-bottom: none; }
.chart-shell {
  background: var(--panel-soft);
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  overflow: hidden;
}
.chart-shell.dark {
  background: rgba(255, 255, 255, 0.65);
  border-color: rgba(32, 40, 51, 0.08);
}
.chart-svg {
  width: 100%;
  height: auto;
  display: block;
}
.segment-matrix {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}
.segment-card {
  min-height: 150px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(255, 253, 248, 0.86);
  border: 1px solid rgba(32, 40, 51, 0.08);
}
.segment-card.featured {
  background: rgba(215, 116, 67, 0.08);
  border-color: rgba(215, 116, 67, 0.18);
}
.segment-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}
.segment-name {
  font-size: 17px;
  line-height: 1.25;
  font-weight: 800;
}
.segment-count {
  padding: 5px 9px;
  border-radius: 8px;
  background: rgba(32, 40, 51, 0.06);
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.segment-desc {
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--muted);
}
.segment-main {
  margin-top: 12px;
  display: grid;
  gap: 4px;
}
.segment-brand {
  font-size: 16px;
  line-height: 1.25;
  font-weight: 800;
  overflow-wrap: anywhere;
}
.segment-meta {
  font-size: 13px;
  line-height: 1.55;
  color: var(--muted);
}
.segment-chips {
  margin-top: 12px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.segment-chip {
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(32, 40, 51, 0.05);
  color: var(--muted);
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.risk-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.risk-card {
  padding: 14px;
  border-radius: 8px;
  background: var(--panel);
  border: 1px solid var(--line);
}
.risk-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.risk-title {
  font-size: 14px;
  font-weight: 700;
}
.level-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(215, 116, 67, 0.14);
  color: #b45309;
  white-space: nowrap;
}
.level-badge.medium { background: rgba(63, 116, 128, 0.14); color: #0f4f5c; }
.level-badge.low { background: rgba(125, 141, 82, 0.14); color: #556b2f; }
.level-badge.wait { background: rgba(114, 120, 135, 0.14); color: #4b5563; }
.risk-basis,
.risk-next {
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.risk-basis { color: var(--text); }
.risk-next { margin-top: 8px; color: var(--muted); }
.footer {
  margin-top: 18px;
  padding-top: 18px;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.65;
}
.footer-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.link-chip {
  background: rgba(32, 40, 51, 0.04);
}
.muted {
  color: var(--muted);
}
@media (max-width: 1220px) {
  .hero,
  .two-col { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .page { padding: 14px; }
  .panel, .subpanel { padding: 18px; border-radius: 8px; }
  .title-en { font-size: 34px; }
  .title-cn { font-size: 15px; }
  .metric-grid,
  .grid-2,
  .grid-3,
  .summary-strip,
  .segment-matrix,
  .risk-grid { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 1fr; }
  .bar-value { justify-self: start; }
}
"""
