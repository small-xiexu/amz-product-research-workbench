# research_core

通用数据结构和规则层。

## 内容

- `schemas/`：统一数据包结构
- `rules/`：利润、状态、风险等通用规则

## 作用

把选品流程里不依赖界面的逻辑先收拢起来，后续 Skill、脚本和网页工作台都复用这里的结构。

## 当前数据契约

- `selection_brief`：模糊选品意图
- `candidate_pool`：候选品池
- `import_manifest`：手动导出文件盘点结果
- `review_voc_package`：自有评论插件导出的 Excel/HTML 转换后的 VOC 数据包
