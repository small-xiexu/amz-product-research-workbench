# Codex 版产物契约

每轮选品必须有一个独立 run 目录。

## 目录结构

```text
runs/<yyyymmdd>_<中文品类方向>/
├── progress.json
├── run_manifest.json
├── mcp_snapshots/
│   ├── sellersprite_quick_snapshot.json
│   ├── sorftime_quick_snapshot.json
│   ├── sellersprite_deep_snapshot.json
│   └── sorftime_deep_snapshot.json
├── quick_check/
│   ├── sellersprite_quick_evidence_packet.json
│   ├── sorftime_quick_evidence_packet.json
│   └── quick_market_gate.json
├── inputs/
│   ├── seller_sprite/                 # 卖家精灵原始导出（只读，不修改）
│   └── reviews/                       # 评论原始导出（只读，不修改）
├── mcp/
│   └── sorftime_verification.json
├── candidate_pool.json
├── route_matrix_confirm.json
├── market_structure/
│   └── market_structure_evidence_packet.json
├── search_demand/
│   └── search_demand_evidence_packet.json
├── conflict_review/
│   └── conflict_resolution_packet.json
├── review_voc/
│   ├── review_voc_package.json
│   ├── voc_evidence_packet.json
│   ├── voc_evidence.xlsx
│   └── voc_gate.json
├── evaluations/
│   ├── market_demand_evaluation.json
│   ├── competition_evaluation.json
│   ├── price_profit_evaluation.json
│   ├── voc_opportunity_evaluation.json
│   ├── risk_evaluation.json
│   ├── data_quality_evaluation.json
│   └── evaluation_summary.json
└── analysis/
    ├── integrated_operator_judgment.json
    ├── <中文品名>_分析报告.html
    ├── <中文品名>_决策工具包.xlsx
    ├── report_data.seed.json
    ├── report_data.json
    ├── delivery_qa_result.json
    ├── qa_notes.md
    ├── qa_notes.round1.md
    └── qa_notes.round2.md
```

**关键约束：**
- `run_id` = `yyyymmdd_中文品类方向`，如 `YYYYMMDD_示例品类`
- `<中文品名>` 与目录名去掉日期前缀一致（`_extract_product_name()` 直接从目录名推导）
- `inputs/` 下是运营手动导出的原始文件，只读不修改
- 所有 AI 笔记、中间 `.md` 文件不放入 run 目录

## 命名规则

| 字段 | 用途 | 例子 |
|---|---|---|
| `run_id` | 本轮运行 ID | `YYYYMMDD_中文品类方向`，如 `YYYYMMDD_示例品类` |
| `product_direction` | 报告主标题 | `<目标方向>` |
| `keyword` | 查询词 | `<目标关键词>` |
| `task_name` | 本轮任务名 | `<站点><目标方向>深挖` |
| `data_sources` | 数据源 | `Sorftime MCP` / `卖家精灵` / `评论插件` |

报告标题只能使用 `product_direction` 或清洗后的候选方向，不得包含：

- `MCP`
- `验证`
- `回归`
- `测试`
- `UI`
- `预览`

这些词只能进入 `data_sources`、`workflow_summary` 或证据说明。

## 必须校验

Stage 7 市场机会报告和最终报告都必须校验。最终正式报告以 `validate_research_outputs.py` 通过为准；Stage 7 以 `analysis/delivery_qa_result.json` 通过或明确待补为准。

Stage 7 最低要求：

- `<中文品名>_分析报告.html`、`<中文品名>_决策工具包.xlsx` 存在（最终交付物）
- `report_data.seed.json`、`report_data.json`、`delivery_qa_result.json` 存在；`report_data.seed.json` 只是脚本初始草稿，`report_data.json` 才是正式数据中枢
- `<中文品名>_分析报告.html` 由 AI 以资深运营专家视角手写，覆盖运营必备板块，用词克制，决策导向
- HTML 包含资深亚马逊运营专家综合分析，不只是多源摘要拼接
- HTML/Excel 是用户可读报告，不能展示 Agent、MCP、tool、internal execution、spawn、packet 等内部执行术语
- Excel 能回表到 Sorftime、卖家精灵、VOC 和证据审计，但 Sheet/标题使用用户可理解名称

最终正式报告最低要求（legacy，当前主链路以 `analysis/` 为最终交付）：

- final_report 五件套存在
- `data.xlsx` 可读取
- 报告结构完整
- Top100 有效明细充足
- 评论 VOC 有证据链，或明确待补
- 市场机会评分卡 8 维完整

## Stage 7 市场机会产物口径

`analysis/` 是多数据源市场机会报告的用户 review 主入口：

- `report_data.seed.json`：**脚本初始草稿**。只提供字段骨架和可自动提取的数据，不是正式交付数据底座，不作为 HTML / XLSX 的最终依据。
- `report_data.json`：**正式数据中枢**。Report Generation Agent 基于 seed 和证据包增强生成；HTML 和 XLSX 均以此文件为准，所有数据声明通过 `source_path` 可追溯到证据包。
- `<中文品名>_分析报告.html`：**最终交付**。AI 以资深亚马逊运营专家视角手写的决策建议书，给人看。HTML 不固定展示“数据来源与口径”板块，可在业务板块中自然表达“样本边界 / 判断口径”。
- `<中文品名>_决策工具包.xlsx`：**最终交付**。脚本生成的运营决策工具包，5 个 Sheet（路线计分卡、竞品拆解、关键词矩阵、样品检查表、冷启动预算），运营可直接使用。
- `delivery_qa_result.json`：**中间产物**。QA Agent 对证据边界、硬缺口和报告完整性的检查。

职责边界：

- 数据源专家 Agent 只产 evidence、缺口、置信度和待补动作，不输出最终报告。
- 脚本先生成 `analysis/report_data.seed.json`。
- Report Generation Agent 以资深亚马逊运营专家身份，基于 seed 增强 `analysis/report_data.json`，再手写 `<中文品名>_分析报告.html`。
- 脚本基于 `analysis/report_data.json` + `integrated_operator_judgment.json` 生成 `<中文品名>_决策工具包.xlsx`（5 Sheet 运营决策工具包）和 `delivery_qa_result.json`。
- 脚本不手写正式 HTML，不重写 Report Generation Agent 产出的正式 `report_data.json`。
- HTML 不暴露 MCP、Agent、tool、packet、source_path、冲突复核过程或内部数据来源分歧；后台 `report_data.json` 和 XLSX 继续保留 source_path 与证据链。

通用模板只能写章节、字段和数据映射，不能写死当前品类、ASIN、关键词或类目。

缺证据表达：

- 系统没有采集、解析或交叉验证到：写“系统侧待补”。
- 需要运营打开 ASIN、关键词结果页、详情页或评论上下文判断：写“人工 review 待补”。
- 只有用户确实未提供必要输入或确认时，才写“用户输入缺失”。

## MCP 产物口径

`mcp/sorftime_verification.json` 和 `search_demand_evidence` 必须保留：

- 类目候选、nodeId、类目角色和来源
- 参考 ASIN、路线和相似理由
- 运营式关键词池
- 关键词月搜、CPC、竞争量和混池标签
- 类目淡旺季和关键词热度的边界说明
- 热销特征、冲突证据和 `data_gaps`

## Stage 4 candidate_pool.json 契约

`candidate_pool.json` 由主 Agent 产出，脚本 `build_mcp_candidate_pool.py` 校验。

```json
{
  "schema_version": "p2-mcp-candidate-pool-v1",
  "source_stage": "market_quick_check",
  "pool_status": "ready_for_route_matrix | needs_user_review | excluded",
  "confidence": "high | medium | low",
  "evidence_refs": ["<路径#片段>..."],
  "generation_provenance": {
    "build_strategy": "agent_generated_script_validated",
    "...": "..."
  },
  "candidates": [
    {
      "candidate_id": "p2-01-<type>-<slug>",
      "name": "<中文候选名称>",
      "candidate_type": "category | keyword | asin | route_seed",
      "status": "继续看 | 观察 | 先放弃",
      "readiness_status": "ready_for_route_matrix | needs_user_review | excluded",
      "reason": "<运营判断理由>",
      "source_agents": ["<Agent 角色名>"],
      "source_refs": ["<路径#片段>"],
      "evidence_refs": ["<路径#片段>"],
      "confidence": "high | medium | low",
      "support_level": "strong | moderate | weak | negative",
      "demand_signal_level": "strong | moderate | weak | unknown",
      "risk_flags": ["<风险标签>"],
      "data_gaps": ["<待补缺口>"],
      "required_deep_dive": ["<深挖项目>"],
      "summary_note": "<一句话总结>"
    }
  ],
  "summary": {
    "total_candidates": "<N>",
    "continue_count": "<N>",
    "trial_count": "<N>",
    "watch_count": "<N>",
    "drop_count": "<N>",
    "key_gaps": ["<关键缺口>"],
    "gate_result": "continue | watch | stop"
  }
}
```

**校验规则**（脚本执行）：
- 结构完整性：`schema_version`、`source_stage`、`pool_status`、`evidence_refs`、`generation_provenance`、`candidates` 均不可缺
- `pool_status` 必须是 `ready_for_route_matrix | needs_user_review | excluded`
- 通用占位符扫描：`candidates[].name`、`candidates[].reason`、`candidates[].summary_note`、`summary.key_gaps` 等语义字段不得包含 `sellersprite|sorftime|mcp|quick_gate|workflow_state`
- 若 `build_strategy == "agent_generated_script_validated"` 且占位符命中 → 阻断，打回 Agent 重写

## Stage 5 route_matrix_confirm.json 契约

`route_matrix_confirm.json` 由主 Agent 产出，脚本 `build_route_matrix_confirm.py` 校验并生成 `data_completeness_check.json`。

```json
{
  "schema_version": "p3-route-matrix-confirm-v1",
  "packet_id": "route_matrix_confirm",
  "run_id": "<run_id>",
  "source_candidate_pool": {
    "path": "candidate_pool.json",
    "pool_status": "<...>",
    "candidate_count": "<N>"
  },
  "route_options": [
    {
      "route_id": "<candidate_id>",
      "route_name": "<中文路线名称>",
      "route_type": "类目路线 | 关键词路线 | 方向路线 | ASIN 路线",
      "role": "排除 | 标准款候选 | 待确认 | 观察",
      "selection_status": "selected | rejected",
      "selection_reason": "<选择/排除理由>",
      "gap_level": "acceptable | warning | blocker",
      "gap_reasons": ["<缺口原因>"],
      "top_products": ["<ASIN>"],
      "route_summary": "<路线总结>"
    }
  ],
  "selected_routes": ["<同 route_options 中 selection_status=selected 的条目>"],
  "rejected_routes": ["<同 route_options 中 selection_status=rejected 的条目>"],
  "decision": "confirm | revise_candidate_pool | stop",
  "decision_reason": "<决策理由>",
  "required_next_actions": ["<下一步动作>"],
  "evidence_refs": ["<路径#片段>..."],
  "voc_readiness": {
    "status": "light_prepared | not_ready",
    "needs_voc_validation": true,
    "routes": ["<路线>"],
    "sample_requirements": ["<采样要求>"]
  }
}
```

**校验规则**（脚本执行）：
- 结构完整性：`route_options`、`selected_routes`、`rejected_routes`、`decision`、`decision_reason`、`required_next_actions`、`evidence_refs`、`voc_readiness` 均不可缺
- `decision` 必须是 `confirm | revise_candidate_pool | stop`
- `route_options` 不可为空
- 通用占位符扫描：`route_name`、`selection_reason`、`decision_reason`、`route_summary`、`gap_reasons` 等语义字段不得包含 `sellersprite|sorftime|mcp|quick_gate|workflow_state`
- 若 `generation_provenance.build_strategy == "agent_generated_script_validated"` 且占位符命中 → 阻断，打回 Agent 重写
