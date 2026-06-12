# research_core

通用数据结构和规则层。

## 内容

- `workflows/`：交互式流程状态推进 + 数据齐全后的批量报告编排
- `contracts/`：核心数据包结构校验，防止错误数据进入下游渲染
- `adapters/`：多数据源适配器，把卖家精灵、Sorftime 等来源转成统一结构
- `schema/`：Python dataclass 形式的规范化产品、关键词、类目结构
- `schemas/`：统一数据包结构
- `rules/`：利润、状态、风险等通用规则

## 作用

把选品流程里不依赖界面的逻辑先收拢起来，后续 Skill、CLI、网页工作台和 API 都复用这里的结构。

当前主产品体验由 `workflows.create_initial_state()`、`workflows.plan_next_action()`、`workflows.advance_stage()` 维护交互状态；`scripts/plan_interactive_workflow.py` 提供最小 CLI。

`scripts/run_research_workflow.py` 保留为数据齐全后的批量报告重跑和回归验证入口。

## 当前数据契约

- `selection_brief`：模糊选品意图
- `candidate_pool`：候选品池
- `import_manifest`：手动导出文件盘点结果
- `review_voc_package`：自有评论插件导出的 Excel/HTML 转换后的 VOC 数据包
- `research_package`：重点候选深挖数据包，供报告渲染层消费
- `workflow_state`：交互式流程状态，记录阶段、下一步动作、运营决策点和证据引用

## 后续扩展落点

- 新增第三方数据中心：优先新增 `adapters/<source>_adapter.py`，再更新 `adapters/merge_strategy.py`
- 新增交互式入口：复用 `workflows.plan_next_action()`，不要把阶段判断写散到脚本里
- 新增批量重跑入口：复用 `workflows.run_research_workflow()`，不要复制 `scripts/run_research_workflow.py`
- 新增数据包强约束：先补 `contracts/validators.py`，再补正式交付校验器
