# report_renderer

报告渲染层。

## 作用

- 读取统一数据包
- 生成 Markdown 主报告
- 生成摘要
- 生成 HTML 看板
- 导出 Excel 底表的文件路径信息
- 生成候选品池预审输出，用于正式深挖前判断候选是否值得继续

## 当前状态

先放最小可用版本，不接 MCP、不做网页。当前包含：

- `render_report.py`：从 `research_package` 生成正式报告骨架。
- `render_candidate_pool.py`：从 `candidate_pool` 生成预审报告、摘要、HTML 看板和 Excel 底表。
