# CLI 双 MCP 多 Agent 选品技术方案

更新日期：2026-06-24

本方案只覆盖 CLI / Skill 主链路。`server/`、`webapp/`、Web 工作台配置页和 API 工具注册暂不改造，等 CLI 版完整可用后再扩展。

目标主链路：运营输入方向 -> 双 Agent 市场快验 -> 候选池 -> 路线矩阵确认 -> 卖家精灵 + Sorftime 双 MCP 深挖 -> 数据归一化 / 冲突复核 -> VOC 评论插件 -> 多评价 Agent -> 资深运营专家判断 -> 正式报告 -> QA。

核心原则：

- 前台报告只给运营判断，不暴露 MCP、Agent、数据冲突、工具调用、source_path。
- 后台证据链完整保留来源、调用参数、冲突、置信度和复核动作。
- 数据 Agent 只产证据包，不输出最终 Go / No-Go。
- 评价 Agent 只打分和列风险，不越权生成最终判断。
- 资深运营专家 Agent 才能给最终综合判断。
- 卖家精灵手动导入从主流程移除，只保留 legacy fallback 和历史回归能力。
- P0 必须先冻结 MCP snapshot schema、Evidence Packet schema、报告契约、QA 规则和 progress 状态机，再进入 P1。

## 范围

| 类型 | 本轮处理 |
|---|---|
| CLI 主流程 | 处理 |
| `skills/amazon-product-research/**` | 处理 |
| `packages/research_core/**` | 处理 |
| `scripts/**` | 处理 |
| `docs/**` 相关契约 | 处理 |
| `runs/<run_id>/` 产物结构 | 处理 |
| `server/**` | 暂不处理 |
| `webapp/**` | 暂不处理 |
| Web 数据源配置 | 暂不处理 |
| Web review task 接口 | 暂不处理 |

## 目标流程

```text
运营输入方向
  ↓
市场快验
  ├─ 卖家精灵 Quick Agent
  └─ Sorftime Quick Agent
  ↓
Quick Gate：继续 / 观察 / 暂停
  ↓
候选池生成
  ↓
路线矩阵确认
  ↓
双 MCP 深挖
  ├─ Market Structure Agent：卖家精灵 MCP
  └─ Search Demand Agent：Sorftime MCP
  ↓
数据归一化 / 冲突复核
  ↓
VOC 评论插件
  ↓
多评价 Agent
  ↓
资深运营专家 Agent
  ↓
报告生成 Agent
  ↓
┌─────────────────────────────────────┐
│  QA 双层强制门禁                      │
│                                       │
│  1. 脚本 QA（自动）                    │
│     fail → 阻断                       │
│     pass ↓                            │
│  2. Delivery QA Agent（独立 spawn）     │
│     pass → 交付                       │
│     fail → 打回报告 Agent 修复         │
│           ↓                           │
│     重新 QA（最多 3 轮）               │
│     3 轮不过 → blocked，人工介入       │
└─────────────────────────────────────┘
```

## 运行目录

每轮选品以 `runs/<run_id>/` 为唯一产物目录。

```text
runs/<run_id>/
├── run_manifest.json
├── workflow_state.json
├── progress.json
├── mcp_snapshots/
│   ├── sellersprite_quick_snapshot.json
│   ├── sorftime_quick_snapshot.json
│   ├── sellersprite_deep_snapshot.json
│   └── sorftime_deep_snapshot.json
├── quick_check/
│   ├── sellersprite_quick_evidence_packet.json
│   ├── sorftime_quick_evidence_packet.json
│   └── quick_market_gate.json
├── candidate_pool.json
├── route_matrix_confirm.json
├── market_structure/
│   └── market_structure_evidence_packet.json
├── search_demand/
│   └── search_demand_evidence_packet.json
├── conflict_review/
│   └── conflict_resolution_packet.json
├── review_voc/
│   ├── voc_gate.json
│   ├── review_voc_package.json
│   ├── voc_evidence_packet.json
│   └── voc_evidence.xlsx
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
    ├── report_data.seed.json
    ├── report_data.json
    ├── <中文品名>_分析报告.html
    ├── <中文品名>_数据回表.xlsx
    ├── delivery_qa_result.json
    ├── qa_notes.md
    ├── qa_notes.round1.md
    └── qa_notes.round2.md
```

### `run_manifest.json`

`run_manifest.json` 记录本轮运行元信息，不承载业务判断。

| 字段 | 说明 |
|---|---|
| `run_id` | run 目录名 |
| `schema_version` | 本轮产物 schema 版本 |
| `skill_version` | 使用的 Skill / Agent 契约版本 |
| `tool_versions` | 脚本、MCP adapter、QA 版本 |
| `mcp_snapshots` | 每个 MCP snapshot 的生成时间、schema、工具清单 |
| `execution_mode` | `real_subagent_spawn` / `serial_fallback` / `script_generated` |
| `legacy_fallback_used` | 是否使用卖家精灵手动导入 fallback |
| `created_at` | 创建时间 |

### MCP Snapshot 固定路径

MCP 原始快照固定落在 `mcp_snapshots/`，Evidence Packet 只能引用这些快照或已生成的上游 packet。

| 文件 | 阶段 | 数据源 |
|---|---|---|
| `mcp_snapshots/sellersprite_quick_snapshot.json` | 市场快验 | 卖家精灵 MCP |
| `mcp_snapshots/sorftime_quick_snapshot.json` | 市场快验 | Sorftime MCP |
| `mcp_snapshots/sellersprite_deep_snapshot.json` | 深挖 | 卖家精灵 MCP |
| `mcp_snapshots/sorftime_deep_snapshot.json` | 深挖 | Sorftime MCP |

### `progress.json`

`progress.json` 是断点恢复台账。每个阶段必须可重入。

顶层结构：

| 字段 | 说明 |
|---|---|
| `schema_version` | progress schema 版本 |
| `current_stage` | 当前阶段 ID |
| `stages` | 按 `stage_id` 分组的阶段状态 |
| `updated_at` | 最近更新时间 |
| `global_blockers` | 跨阶段阻塞项 |
| `next_action` | 当前最小下一步 |
| `completed_artifacts` | 已校验可复用的产物 |

每个 `stages.<stage_id>`：

| 字段 | 说明 |
|---|---|
| `status` | `pending` / `running` / `done` / `blocked` / `failed` / `needs_user` |
| `attempts` | 执行次数 |
| `input_artifacts` | 本阶段读取的 artifact |
| `output_artifacts` | 本阶段必须生成的 artifact |
| `validation_checks` | 阶段完成前必须通过的检查 |
| `last_error` | 失败原因 |
| `next_required_user_action` | 等待运营时必须填写 |
| `resume_policy` | 重跑时是否复用已有 artifact、是否允许重复 MCP 调用 |

推进规则：

- 阶段 `done` 后才能进入下一阶段。
- 阶段 `failed` 重跑时先读取已有 artifact，除非 schema 过期或校验失败，不重复调用 MCP。
- 阶段 `needs_user` 必须写清运营下一步动作。
- 任一阻塞 artifact 缺失时，不生成正式报告。

## 阶段设计

| 阶段 | 参与 Agent / 模块 | 输入 | 输出 | 运营是否参与 |
|---|---|---|---|---|
| 1. 运营输入 | 主 Agent | 方向、关键词、ASIN、站点、禁区、偏好 | `workflow_state.json`、`progress.json` | 是 |
| 2. 市场快验 | 卖家精灵 Quick Agent、Sorftime Quick Agent | 运营输入 | 双 quick evidence packet | 否 |
| 3. 快验门控 | Quick Gate | 双 quick evidence packet | `quick_market_gate.json` | 必要时确认 |
| 4. 候选池 | Candidate Pool Builder | quick gate、双 quick packet | `candidate_pool.json` | 是 |
| 5. 路线矩阵 | Route Matrix Builder | candidate pool | `route_matrix_confirm.json` | 是 |
| 6. 双 MCP 深挖 | Market Structure Agent、Search Demand Agent | route matrix、候选 ASIN、关键词、类目 | 两个正式 evidence packet | 否 |
| 7. 冲突复核 | Conflict Resolver | 双正式 evidence packet | `conflict_resolution_packet.json` | 仅阻塞时确认 |
| 8. VOC | VOC Evidence Agent | 评论插件导出 / JSON、ASIN 批次 | `voc_gate.json`、`review_voc_package.json`、`voc_evidence_packet.json` | 是 |
| 9. 多评价 | 多个评价 Agent | 三类证据包、冲突包、路线矩阵 | `evaluations/*.json` | 否 |
| 10. 综合判断 | 资深运营专家 Agent | evidence packets、evaluation summary | `integrated_operator_judgment.json` | 否 |
| 11. report_data seed | 脚本 | integrated judgment、证据包 | `report_data.seed.json` | 否 |
| 12. 正式报告 | Report Generation Agent | seed、integrated judgment | `report_data.json`、HTML | 否 |
| 13. 回表与 QA | 脚本（自动） + Delivery QA Agent（强制独立 spawn） | `report_data.json`、HTML、证据包、MCP snapshots | XLSX、`delivery_qa_result.json`、`qa_notes.md` | 失败时进入修复循环（最多 3 轮） |

## P0 契约冻结

P0 是本方案的实施前置，不产正式选品报告。

| 契约 | P0 验收 |
|---|---|
| MCP smoke call | 卖家精灵 MCP、Sorftime MCP 均完成最小真实调用，记录工具名、参数、成功/失败样例 |
| snapshot schema | 固化 quick / deep 两类 snapshot 字段、空结果、限流、超时、失败格式 |
| schema version | 所有 snapshot、packet、progress、report_data 明确 `schema_version` |
| Evidence Packet | 固化 quick、deep、conflict、evaluation、integrated judgment 的必填字段 |
| report_data 职责 | 明确脚本生成 seed，Agent 只能补运营判断字段和非数字分析 |
| HTML 报告契约 | 删除“数据来源与口径”固定板块，保留“判断口径 / 样本边界”表达 |
| QA 规则 | 同步 required section、source_path 校验、内部术语泄漏、冲突泄漏检查 |
| progress 状态机 | 固化阶段状态、可重入条件、失败恢复策略 |
| report 生命周期 | 固化 seed、Agent 增强、HTML、XLSX、QA 的职责边界 |
| integrated judgment | 固化资深运营专家最终判断 schema |
| artifact 路径 | 固化 MCP snapshot、VOC Gate、report_data seed 路径 |
| candidate pool 入口 | 明确吸收、重命名或废弃 `scripts/build_fused_candidate_pool.py` |

### MCP snapshot 基础结构

所有 MCP snapshot 必须先落盘，再由 Adapter 转换成 Evidence Packet。

```json
{
  "schema_version": "mcp-snapshot-v1",
  "source_type": "seller_sprite_mcp | sorftime_mcp",
  "stage": "market_quick_check | deep_dive",
  "depth": "quick | deep",
  "collected_at": "ISO-8601",
  "marketplace": "US",
  "tool_calls": [],
  "raw_results": {},
  "normalized_preview": {},
  "errors": [],
  "rate_limit": {},
  "data_gaps": []
}
```

标准失败格式：

| 场景 | 写法 |
|---|---|
| 空结果 | `errors=[]`，`data_gaps` 写明空结果影响 |
| 超时 | `errors[].type=timeout`，保留可复用的已成功调用 |
| 限流 | `errors[].type=rate_limited`，写入 retry_after 或降级动作 |
| 参数不支持 | `errors[].type=invalid_params`，写入工具名和参数摘要 |
| 工具不可用 | `errors[].type=tool_unavailable`，阶段状态改为 `blocked` 或 `failed` |

### Evidence Packet 必填字段

所有 Evidence Packet 强制包含：

| 字段 | 说明 |
|---|---|
| `schema_version` | packet schema 版本 |
| `packet_id` | 固定 ID |
| `stage` | 所属阶段 |
| `depth` | `quick` / `deep` / `evaluation` / `final` |
| `source_type` | 数据源或 Agent 类型 |
| `collected_at` | 采集或生成时间 |
| `data_window` | 数据时间窗 |
| `confidence` | `high` / `medium` / `low` |
| `facts` | 可追溯事实 |
| `derived_metrics` | 派生指标 |
| `metric_basis` | 数值型事实 / 派生指标的可比较口径；也可内联到单条 fact / metric |
| `data_gaps` | 缺口及影响 |
| `evidence_refs` | 指向 snapshot、评论、MCP 工具调用或上游 packet |
| `execution_provenance` | 真实子 Agent、串行模拟、脚本生成或 legacy fallback |

`evidence_refs` 统一引用格式：

- `mcp_snapshots/sellersprite_quick_snapshot.json#tool_calls[0]`
- `market_structure/market_structure_evidence_packet.json#facts.price_bands[0]`
- `review_voc/review_voc_package.json#normalized_reviews[12]`

## 市场快验

市场快验是方向过滤器，不是正式深挖的缩小版。它只回答“有没有必要继续看”。

### 卖家精灵 Quick Agent

职责：

- 看大盘容量。
- 看候选类目和 Top 产品结构。
- 看价格带是否健康。
- 看销量 / 销售额结构。
- 看 Review 门槛和低评论有量样本。
- 看品牌 / 商品集中度是否过高。
- 初步识别明显混池方向。

输出：`quick_check/sellersprite_quick_evidence_packet.json`

禁止：

- 不写正式报告。
- 不给最终 Go / No-Go。
- 不替 Sorftime 判断搜索需求。
- 不把大盘容量直接等同于进入机会。

### Sorftime Quick Agent

职责：

- 看核心关键词是否有搜索量。
- 看搜索意图是否匹配目标产品。
- 看关键词首页是否混池。
- 看候选类目、相似品和关联品。
- 看类目趋势、关键词趋势和流量入口。
- 初步判断哪些关键词 / ASIN 值得后续深挖。

输出：`quick_check/sorftime_quick_evidence_packet.json`

禁止：

- 不写正式报告。
- 不给最终 Go / No-Go。
- 不用关键词搜索量替代市场销量。
- 不把关键词映射类目当成最终类目。

### Quick Gate

输入：

- `sellersprite_quick_evidence_packet.json`
- `sorftime_quick_evidence_packet.json`

输出：`quick_check/quick_market_gate.json`

字段：

| 字段 | 说明 |
|---|---|
| `gate_result` | `continue` / `watch` / `stop` |
| `reason` | 一句话说明快验判断 |
| `candidate_seeds` | 建议进入候选池的方向、关键词、ASIN 或类目 |
| `excluded_directions` | 明显混池、过宽或不建议继续的方向 |
| `required_deep_dive` | 深挖阶段必须补的类目、关键词、ASIN、VOC |
| `data_gaps` | 快验缺口 |
| `confidence` | `high` / `medium` / `low` |

Quick Packet 必须给 Quick Gate 的可测字段：

| 字段 | 取值 |
|---|---|
| `support_level` | `strong` / `moderate` / `weak` / `negative` |
| `blocking_gaps` | 阻塞缺口列表 |
| `mixed_pool_level` | `none` / `mild` / `material` / `blocking` |
| `demand_signal_level` | `strong` / `moderate` / `weak` / `unknown` |
| `price_band_health` | `healthy` / `watch` / `weak` / `unknown` |
| `category_boundary_clarity` | `clear` / `partial` / `unclear` / `blocking` |

门控规则：

- `continue`：两源均支持继续，或一源强支持且另一源无关键反证。
- `watch`：方向可能成立，但类目、关键词或竞品边界不清。
- `stop`：两源均显示需求弱、严重混池、价格带不可做或头部壁垒过高。

Quick Gate 默认门控：

| 条件 | `gate_result` |
|---|---|
| 任一 `blocking_gaps` 非空 | `stop` |
| 两源 `support_level=negative` | `stop` |
| 任一字段为 `blocking` 级别 | `stop` |
| 两个 Quick Packet `support_level in {strong, moderate}` 且无 `blocking_gaps` | `continue` |
| 一源 `support_level=strong`，另一源不为 `negative`，但存在 `unknown` 字段 | `watch` |
| 任一源 `mixed_pool_level=material` | `watch` |
| 任一源 `mixed_pool_level=blocking` | `stop` |
| 两源都缺核心字段 | `stop` |
| `price_band_health=weak` 且 `demand_signal_level` 不强 | `watch` 或 `stop` |
| `category_boundary_clarity=blocking` | `stop` |

优先级：`stop` 高于 `watch`，`blocking_gaps` 高于 `support_level`，其余冲突默认进入 `watch`。

## 双 MCP 深挖

路线矩阵确认后才进入正式深挖。正式深挖比快验更完整，目标是支撑报告和最终判断。

### Market Structure Agent

数据源：卖家精灵 MCP。

核心输出：`market_structure/market_structure_evidence_packet.json`

覆盖：

- Top 产品结构。
- 类目容量。
- 价格带机会。
- 销量 / 销售额结构。
- Review 分布。
- 商品集中度、品牌集中度、卖家集中度。
- 新品机会。
- 参考 ASIN 池。
- ABA / 关键词反查中与市场结构相关的信号。

### Search Demand Agent

数据源：Sorftime MCP。

核心输出：`search_demand/search_demand_evidence_packet.json`

覆盖：

- 核心关键词。
- 主要流量词。
- 转化优质词。
- 精准长尾词。
- 混池 / 排除词。
- ASIN 流量词。
- 竞品自然位关键词。
- 关键词搜索结果结构。
- 相似品和关联品。
- 类目路径辅助验证。
- 类目趋势和关键词趋势。

## 数据归一化与冲突复核

输出：`conflict_review/conflict_resolution_packet.json`

冲突不写进最终报告，但必须留在后台。

| 指标类型 | 默认优先口径 |
|---|---|
| 月销量、月销售额、Top100、价格带、集中度 | 卖家精灵优先 |
| ABA、关键词反查中的转化 / 点击信号 | 卖家精灵优先 |
| 搜索词扩展、自然位、ASIN 流量词、类目趋势 | Sorftime 优先 |
| 类目归属 | 参考 ASIN 反推 + 双源交叉 |
| 价格、评分、Review 数 | 双源交叉，差异大时复核 |
| VOC 痛点 | 评论插件原始评论优先 |

冲突分级：

| 等级 | 判定 | 处理 |
|---|---|---|
| `minor` | 数值差异小，不影响判断 | 记录但不阻塞 |
| `material` | 影响价格带、需求规模或竞争判断 | 触发复核，报告中转成谨慎判断 |
| `blocking` | 影响是否继续看 | 暂停，要求补数或人工确认 |

### 可比较性前置

Conflict Resolver 先判断两个指标是否可比较，再判断冲突等级。不可比较时不直接计算差异，写入 `basis_mismatch`。

每个可比较指标必须带 `metric_basis`：

| 字段 | 说明 |
|---|---|
| `marketplace` | 站点 |
| `currency` | 币种 |
| `data_window` | 7 天 / 30 天 / 月度等 |
| `aggregation_unit` | `asin` / `parent_asin` / `keyword` / `category` |
| `sample_scope` | Top100、搜索结果页、竞品池、关键词池等 |
| `collected_at` | 采集时间 |

`metric_basis` 不一致的处理：

| 场景 | 处理 |
|---|---|
| 币种不同 | 先换算，否则不可比较 |
| 数据窗口不同 | 标记 `basis_mismatch`，不按百分比判冲突 |
| 父体 / 子体不同 | 标记 `basis_mismatch`，要求复核 |
| 站点不同 | `blocking`，除非明确是对照市场 |
| 样本范围不同 | 只做方向性参考，不用于强结论 |

默认阈值：

| 字段 | `material` | `blocking` |
|---|---|---|
| 价格 | 双源差异 > 10% | 影响目标价格带判断且无法复核 |
| Review 数 | 双源差异 > 15% | 影响评论门槛判断且无法复核 |
| 月销量 | 双源差异 > 20% | 影响是否继续看且无可信优先源 |
| 月销售额 | 双源差异 > 20% | 影响市场容量判断且无可信优先源 |
| 评分 | 双源差异 > 0.3 | 影响质量判断且无评论证据支撑 |
| 类目归属 | 核心类目不一致 | 影响路线选择 |
| 关键词意图 | 首页搜索结果明显混池 | 主流搜索意图不指向目标产品 |
| 关键字段缺失 | 单源缺失 | 双源都缺，且影响当前阶段判断 |
| VOC 样本 | 有效评论 < 30 或低分评论 < 10 | 仍试图输出强痛点结论 |

Conflict Resolver 输出必须包含：

- `conflict_id`
- `field`
- `scope`：ASIN / 类目 / 关键词 / 路线
- `source_values`
- `severity`
- `preferred_value`
- `preferred_reason`
- `required_action`
- `report_expression_hint`

最终报告表达方式：

- 不写“两个数据源冲突”。
- 不写“卖家精灵显示 / Sorftime 显示”。
- 用运营语言表达为“需求稳定性需验证”“类目边界需复核”“销量质量不宜直接放大”。

## VOC 评论插件

VOC 只在路线值得继续后接入，不在快验阶段提前抓。

### VOC Gate

评论采集前必须先生成并确认 VOC Gate。

输出：`review_voc/voc_gate.json`

| 字段 | 说明 |
|---|---|
| `target_marketplace` | 目标站点 |
| `review_asin_batch` | ASIN 批次 |
| `route_coverage` | 每条路线覆盖的 ASIN 数 |
| `asin_roles` | 主推、高销量、新品、高客单、痛点、混池对照 |
| `min_review_requirements` | 有效评论、低分评论最低要求 |
| `review_time_window` | 评论时间窗 |
| `mixed_pool_controls` | 混池对照样本 |
| `expected_export_format` | Excel / JSON / HTML 辅助 |
| `parse_readiness` | 是否可被导入脚本解析 |
| `next_required_user_action` | 给运营的复制 ASIN / 导出动作 |

VOC Gate 未通过时，不进入 `review_voc_package.json` 生成。

输入：

- 路线矩阵。
- 参考 ASIN 池。
- 主推路线、升级路线、新品样本、痛点样本、混池对照样本。
- 评论插件 Excel / HTML / JSON。

输出：

- `review_voc/review_voc_package.json`
- `review_voc/voc_evidence_packet.json`
- `review_voc/voc_evidence.xlsx`

VOC Agent 职责：

- 识别用户真实痛点。
- 识别好评驱动。
- 把痛点转成规格要求、样品测试项或 Listing 风险。
- 检查评论样本是否覆盖路线和 ASIN 角色。
- 标注样本不足、低分不足、站点 / 评论地区口径不清等问题。

禁止：

- 不判断市场能不能做。
- 不把评论痛点当市场规模。
- 不使用 HTML AI 报告替代评论明细证据。

## 多评价 Agent

评价 Agent 只输出分项评分，不输出最终结论。

| Agent | 输出文件 | 核心问题 |
|---|---|---|
| 市场需求评价 Agent | `evaluations/market_demand_evaluation.json` | 需求是否真实、稳定、足够大 |
| 竞争结构评价 Agent | `evaluations/competition_evaluation.json` | 是否头部垄断、评论门槛是否过高 |
| 价格利润评价 Agent | `evaluations/price_profit_evaluation.json` | 价格带是否健康，有无利润想象空间 |
| VOC 机会评价 Agent | `evaluations/voc_opportunity_evaluation.json` | 痛点能否转成产品差异化 |
| 风险评价 Agent | `evaluations/risk_evaluation.json` | 合规、季节性、退货、体积、售后、同质化风险 |
| 数据质量评价 Agent | `evaluations/data_quality_evaluation.json` | 样本是否足够，是否混池，是否有阻塞冲突 |

统一输出字段：

| 字段 | 说明 |
|---|---|
| `score` | 0-100 |
| `rating` | `strong` / `watch` / `weak` / `blocked` |
| `key_reasons` | 支撑评分的事实和推断 |
| `risks` | 该维度风险 |
| `required_followups` | 下一步验证动作 |
| `evidence_refs` | 指向 evidence packet 字段 |
| `confidence` | 置信度 |

聚合输出：`evaluations/evaluation_summary.json`

### Evaluation Summary 治理规则

`evaluation_summary.json` 不做机械加权，只做约束治理。

维度分层：

| 类型 | 维度 |
|---|---|
| 核心维度 | `market_demand`、`competition`、`price_profit`、`data_quality` |
| 辅助维度 | `voc_opportunity`、`risk` |

风险维度阻塞规则：

| 风险类型 | 处理 |
|---|---|
| 合规 / 知产 `blocked` | 最终不能 Go |
| 退货 / 售后 `blocked` | 最终不能 Go，除非有明确可验证缓解动作 |
| 体积 / 运费 `blocked` | 最终进入 `watch` 或 `blocked` |
| 季节性 `blocked` | 不一票否决，但必须限制备货和验证窗口 |

| 规则 | 处理 |
|---|---|
| 任一核心维度 `rating=blocked` | 最终判断不能直接 Go |
| `data_quality=blocked` | 最终只能是“补数后再判断” |
| `confidence=low` | 不得支撑强结论，只能作为观察 |
| 分数冲突 | 资深运营专家必须解释采纳或弱化原因 |
| VOC 机会强但市场需求弱 | 不得直接推进产品定义 |
| 市场需求强但竞争 / 价格 blocked | 不得直接 Go |
| 多数评价 weak | 默认进入暂停或补证据 |

`evaluation_summary.json` 必填：

- `dimension_results`
- `blocked_dimensions`
- `low_confidence_dimensions`
- `cross_dimension_tensions`
- `operator_judgment_constraints`
- `recommended_final_verdict_range`

## 资深运营专家 Agent

输出：`analysis/integrated_operator_judgment.json`

必填字段：

| 字段 | 说明 |
|---|---|
| `schema_version` | judgment schema 版本 |
| `final_verdict` | `go` / `watch` / `no_go` / `blocked` |
| `verdict_reason` | 最终判断理由 |
| `recommended_route` | 推荐路线 |
| `rejected_routes` | 不推荐路线及原因 |
| `biggest_opportunity` | 最大机会 |
| `biggest_risk` | 最大风险 |
| `required_next_actions` | 下一步验证动作 |
| `constraints_applied` | 来自 evaluation summary / conflict / QA 的限制 |
| `evidence_refs` | 指向 evidence packet、evaluation、conflict |
| `confidence` | `high` / `medium` / `low` |

职责：

- 读取三类 evidence packet、冲突复核包和评价汇总。
- 给出是否值得继续。
- 给出最推荐路线和不推荐路线。
- 判断最大机会、最大风险和下一步验证动作。
- 判断是否进入产品定义 / 样品 / 供应链验证阶段。

禁止：

- 不新增证据包外的数字。
- 不把评价 Agent 的分数机械相加成最终结论。
- 不把数据冲突过程写进最终报告。

## 报告生成 Agent

输出：

- `analysis/report_data.json`
- `analysis/<中文品名>_分析报告.html`

报告只给运营看，必须像成熟运营专家写的分析报告。

报告生命周期固定为三段：

| 阶段 | 责任方 | 输入 | 输出 |
|---|---|---|---|
| 1. Seed | 脚本 | analysis packet、evidence packets、integrated judgment | `report_data.seed.json` |
| 2. 报告增强 | Report Generation Agent | `report_data.seed.json`、integrated judgment | `report_data.json`、HTML |
| 3. 回表与 QA | 脚本 | `report_data.json`、HTML、evidence packets | XLSX、`delivery_qa_result.json` |

`build_analysis_report.py` 职责：

- 可以生成 `report_data.seed.json`。
- 可以基于 `report_data.json` 生成 XLSX。
- 可以运行 Delivery QA。
- 不负责手写最终 HTML。
- 如果兼容旧链路需要生成占位 HTML，必须标记为 `draft`，不得作为正式交付。

`report_data.json` 边界：

- Agent 只能补充运营判断字段、解释性文本、风险表达和下一步动作。
- Agent 不得新增 seed / evidence packet 里不存在的数字。
- 所有数字必须有 `source_path`，且可追溯到 Evidence Packet。
- QA 只校验 `report_data.json` 到 Evidence Packet 的 source_path 和数值一致性。

报告允许出现：

- 市场结论。
- 机会判断。
- 竞争格局。
- 用户痛点。
- 推荐路线。
- 风险和验证动作。
- Go / No-Go 建议。

报告禁止出现：

- MCP。
- Agent。
- tool / spawn / packet / pipeline。
- source_path。
- 某某数据源显示。
- 两个数据源冲突。
- 工具调用、参数、返回时间。
- 内部执行模式。

现有报告契约需要调整：

- HTML 可保留“样本边界 / 判断口径”表达，但不展示“数据来源与口径”这种开发向板块。
- `report_data.json` 继续保留 `source_path` 和证据来源，供 QA 使用。
- Excel 回表可以保留证据链 Sheet，但正式 HTML 不暴露内部来源过程。
- Delivery QA 的 required section markers 必须同步调整，避免旧 QA 要求“数据来源与口径”板块导致新报告被拦截。

## QA（双层强制门禁）

QA 是交付前的最后一道门禁，分为两层，**两层都必须通过才能交付**，不可跳过、不可降级。

```
build_analysis_report.py 生成 XLSX 后
          │
          ├─ 1. 脚本 QA（自动执行，不可跳过）
          │     确定性机械检查：板块完整性、禁止术语正则、
          │     source_path 可解析性、数值一致性抽查、P0 阻塞项
          │     → analysis/delivery_qa_result.json
          │     fail → 阻断，打回对应阶段修复
          │
          └─ 2. Delivery QA Agent（强制独立 spawn，不可跳过）
                独立子 Agent，读取 HTML + report_data.json +
                全部 evidence packets + MCP snapshots
                首要职责：数据真实性交叉核对（防胡编乱造）
                次要职责：运营判断质量、越权检测
                → analysis/qa_notes.md
                pass → 交付
                fail → 打回 Report Generation Agent 修复，重新 QA
```

### 脚本 QA

输出：`analysis/delivery_qa_result.json`

确定性检查项：

- 文件完整性：`report_data.json`、HTML、XLSX 是否存在。
- 板块完整性：HTML 是否包含 6 个运营必备板块；`report_data.json` 是否包含 11 个板块和 2 个声明。
- 禁止术语扫描：HTML 中不得出现 Agent、MCP、tool、spawn、packet、pipeline、source_path、snapshot、schema_version、execution_provenance、卖家精灵（作为数据源）、Sorftime（作为数据源）。
- 数据源泄漏扫描：HTML 中不得出现“两个数据源”“数据冲突”“数据不一致”“卖家精灵显示/Sorftime 显示”等冲突过程表述。
- source_path 可解析性：`report_data.json` 中每个 `source_path` 能否在 evidence packet 中定位到真实字段。
- 数值一致性抽查：`report_data.json` 中的值与 evidence packet 中对应字段的值是否一致（容忍 5% 精度差异）。
- P0 阻塞项：blocking conflict 未解决、`data_quality=blocked`、`confidence=low` 强结论、progress 未完成、schema_version 不一致。

脚本 QA fail 时阻断交付流程，不进入 Agent QA。

### Delivery QA Agent（强制独立子 Agent）

输出：`analysis/qa_notes.md`

#### 调度规则

- **强制 spawn**：必须是独立子 Agent，不允许主 Agent 自检替代。
- **不可跳过**：脚本 QA pass 后强制执行，不通过不得交付。
- **每次重跑都是新 spawn**：确保上下文独立，不受上一轮 QA 或 Report Generation Agent 影响。
- 如果环境不支持 spawn：标记为 `blocked`，不得以降级方式（主 Agent 自检）交付。

#### 首要职责：数据真实性交叉核对（防胡编乱造）

Agent 必须实际打开文件、读取数值、逐条交叉比对。三级追溯链：

```
HTML 报告中的数字
    ↓ 能找到对应条目吗？
report_data.json 中的 value + source_path
    ↓ source_path 能追溯到吗？
evidence packet 中的 facts / derived_metrics
    ↓ evidence_refs 能追溯到吗？
MCP snapshot 中的原始返回字段
```

| 检查项 | 级别 | 判定规则 |
|---|---|---|
| HTML 数字在 report_data.json 中无对应 | blocker | 提取 HTML 中所有数字（销量、价格、评分、占比、增长率），逐一在 report_data.json 中查找匹配条目 |
| report_data.json 的 source_path 空或无效 | blocker | `source_path` 为空字符串、`__ai_pending__` 未替换、或指向不存在的文件/字段 |
| evidence packet 字段在 MCP snapshot 中无对应 | blocker | 沿 evidence_refs 链追溯到 snapshot，字段不存在 |
| 数值在三级链路中不一致 | blocker | HTML 写 5000，report_data 写 3000，evidence 写 3200 → 查明哪个环节被篡改 |
| 报告中出现 evidence packet 中不存在的数字 | blocker | evidence 无退货率数据，报告却写“退货率约 8%” → 纯属捏造 |
| 派生计算错误 | blocker | evidence 中 Top10 月销之和 5 万，报告写“Top10 占比 90%”，但总容量 10 万 → 算错 |

#### 次要职责：运营判断质量

| 检查项 | 级别 | 判定规则 |
|---|---|---|
| 只堆数据不下判断 | blocker | 没有“建议进入/补齐/暂停”的明确结论 |
| 数据质量 low confidence 但强结论 | blocker | `confidence=low` 的维度却用确定语气下强进入结论 |
| 评价 blocked 却给 Go | blocker | evaluation_summary 中核心维度 blocked，报告却建议 Go |
| VOC 痛点无法追溯到评论原文 | blocker | 抽查 5 条痛点，逐条在 voc_evidence_packet 中找对应 review_id 和原文 |
| 过度乐观 | error | 全篇利好不提风险，或对明显风险轻描淡写 |
| 关键词未分层 | error | 缺少流量词/转化词/长尾词/混池词分类 |
| 参考 ASIN 明显不相似 | error | Agent 读 ASIN 标题和类目能判断对标错误 |
| 内部术语/数据源泄漏 | blocker | 与脚本 QA 相同的禁止项，Agent 做语义层复查 |
| 冲突过程泄漏 | blocker | 报告中出现“两个数据源”“XX显示/YY显示”等后台冲突语言 |

#### QA → 修复 → 再 QA 循环

Delivery QA Agent 不通过时，不是直接放弃，而是进入修复循环：

```
Report Generation Agent 生成报告
    ↓
Delivery QA Agent（独立 spawn）核查
    ↓
┌─ pass → 交付
└─ fail → qa_notes.md 写入可执行修复清单
            ↓
         打回 Report Generation Agent 修复
            ↓
         Delivery QA Agent（重新独立 spawn）再核查
            ↓
┌─ pass → 交付
└─ fail → 再次打回（最多 3 轮）
            ↓
         3 轮不过 → 标记 blocked，需人工介入
```

**修复循环规则**：

- 最多 **3 轮**。3 轮 QA 仍不通过 → `progress.json` 中 `stage_10_qa` 标记为 `blocked`，`next_required_user_action` 写清阻塞原因。
- `qa_notes.md` 必须是**可执行的修复清单**，精确到行级别：`"第 X 段第 Y 个数字，报告写 5000，证据包是 3200，请修正为 3200 或标注为估算"`。不得写模糊反馈如“报告质量不行”。
- 每次 QA 重跑必须是**新的独立 spawn**，拥有独立上下文。
- 每轮 QA 的 `qa_notes.md` 保留不覆盖，文件名加轮次后缀：`qa_notes.md`（最新轮）、`qa_notes.round1.md`、`qa_notes.round2.md`。
- Report Generation Agent 修复时只能修改报告内容和 `report_data.json`，**不得修改 evidence packet 或 MCP snapshot**。

#### progress.json 状态流转

`stage_10_qa` 阶段状态：

| 状态 | 含义 |
|---|---|
| `pending` | 等待脚本 QA pass |
| `running` | Delivery QA Agent 正在核查（第 N 轮） |
| `needs_fix` | QA 不通过，打回 Report Generation Agent 修复 |
| `done` | QA pass，可以交付 |
| `blocked` | 3 轮 QA 仍不通过，需人工介入 |

#### qa_notes.md 输出格式

```markdown
# QA 审核记录 — 第 N 轮

## 1. 数据真实性核对
- 核对数字总数：XX 条
- 可追溯至 MCP snapshot：XX 条
- 无法追溯（blocker）：XX 条
  | 报告位置 | 报告数值 | source_path | 问题 |
  |---------|---------|-------------|------|
  | 价格带段第2段 | 月销5000 | market_structure.facts.top_products[3].monthly_units | evidence中为3200 |
- 凭空出现无证据的数字（blocker）：XX 条
  | 报告位置 | 报告数值 | 问题 |
  |---------|---------|------|
  | 风险段第3段 | 退货率约8% | evidence中无退货率数据 |

## 2. 运营判断质量
- 判词与评价汇总一致性：通过/不通过
- 明确结论：有/无
- VOC 痛点溯源抽查（5条）：通过 X / 不通过 Y
- 过度乐观：是/否

## 3. 禁止项扫描
- 内部术语泄漏：有/无
- 数据源泄漏：有/无
- 冲突过程泄漏：有/无

## 4. 裁决
- [ ] 通过 — 可以交付
- [ ] 不通过 — 打回 Report Generation Agent 修复（第 N 轮，剩余 M 轮）

审核人：Delivery QA Agent（独立子 Agent）
审核时间：ISO-8601
```

## 现有文件改造映射

| 文件 / 目录 | 改造方向 |
|---|---|
| `skills/amazon-product-research/SKILL.md` | 重写阶段流程：卖家精灵导出改为双 MCP；新增双 Agent 快验、多评价 Agent |
| `skills/amazon-product-research/agents/market-structure-agent.md` | 数据源从卖家精灵导出改为卖家精灵 MCP；增加 quick / deep 两种模式 |
| `skills/amazon-product-research/agents/search-demand-agent.md` | 增加 quick / deep 两种模式；快验输出独立 quick packet |
| `skills/amazon-product-research/agents/voc-evidence-agent.md` | 保持主职责，补充与路线矩阵、评价 Agent 的交接字段 |
| `skills/amazon-product-research/agents/report-generation-agent.md` | 强化最终 HTML 不暴露来源、冲突、Agent、MCP；调整“数据来源与口径”板块 |
| `skills/amazon-product-research/agents/delivery-qa-agent.md` | 重写：强制独立 spawn、数据真实性三级交叉核对（HTML→report_data→evidence→MCP snapshot）、运营判断质量、修复循环（最多 3 轮）、可执行修复清单输出 |
| `skills/amazon-product-research/references/multi_agent_dispatch.md` | Delivery QA Agent 从“可 spawn”改为“强制 spawn”；新增 QA→报告 Agent 修复循环编排 |
| `skills/amazon-product-research/references/evidence_packet_contract.md` | 新增 quick packet、conflict packet、evaluation packet、integrated judgment 契约 |
| `docs/卖家精灵导出指令完整性规范.md` | 降级为 legacy fallback 文档 |
| `docs/字段来源表.md` | 更新卖家精灵字段来源为 MCP 主路径 |
| `docs/正式报告契约.md` | 去掉正式 HTML 对数据来源过程的展示要求 |
| `packages/research_core/adapters/seller_sprite_adapter.py` | 从导出记录适配扩展为 MCP snapshot 适配；旧导入适配保留 legacy |
| `packages/research_core/adapters/sorftime_adapter.py` | 对齐 quick / deep snapshot 字段 |
| `packages/research_core/adapters/merge_strategy.py` | 扩展冲突优先级和冲突分级输出 |
| `packages/research_core/pipeline/build_candidate_pool_from_import_manifest.py` | 主路径改为从 quick gate / MCP evidence 构建候选池；导入 manifest 仅 fallback |
| `packages/research_core/pipeline/build_analysis_packet.py` | 增加 conflict、evaluations、integrated judgment 读取 |
| `packages/research_core/pipeline/delivery_qa.py` | 增加数据源泄漏、冲突泄漏扫描；补全禁止术语模式；增强 source_path 追溯至 MCP snapshot |
| `scripts/inspect_manual_exports.py` | 保留 fallback，不再作为主流程必经入口 |
| `scripts/build_candidate_pool_from_import_manifest.py` | 保留 fallback；新增 MCP 版候选池入口 |
| `scripts/build_fused_candidate_pool.py` | P0 决策：废弃为历史原型，不吸收、不重命名为 MCP 主入口；该脚本含样例硬编码，未清理前不得作为通用主链路 |
| `scripts/build_analysis_report.py` | 生成 `report_data.seed.json`、基于 `report_data.json` 生成 XLSX、运行 QA；不负责手写正式 HTML |

## 新增建议文件

| 文件 | 作用 |
|---|---|
| `skills/amazon-product-research/agents/market-demand-evaluation-agent.md` | 市场需求评价 |
| `skills/amazon-product-research/agents/competition-evaluation-agent.md` | 竞争结构评价 |
| `skills/amazon-product-research/agents/price-profit-evaluation-agent.md` | 价格利润评价 |
| `skills/amazon-product-research/agents/voc-opportunity-evaluation-agent.md` | VOC 机会评价 |
| `skills/amazon-product-research/agents/risk-evaluation-agent.md` | 风险评价 |
| `skills/amazon-product-research/agents/data-quality-evaluation-agent.md` | 数据质量评价 |
| `skills/amazon-product-research/agents/lead-operator-agent.md` | 资深运营专家综合判断 |
| `packages/research_core/pipeline/build_quick_market_gate.py` | 双 quick packet 生成快验门控 |
| `packages/research_core/pipeline/build_conflict_resolution_packet.py` | 双源冲突复核 |
| `packages/research_core/pipeline/build_evaluation_summary.py` | 评价 Agent 汇总 |
| `scripts/build_mcp_candidate_pool.py` | P2 新建 MCP 主路径候选池入口；不得依赖 `build_fused_candidate_pool.py` 的硬编码样例逻辑 |

## 实施顺序

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0 | 契约冻结 | MCP smoke call、quick/deep snapshot schema、Evidence Packet schema、report 生命周期、integrated judgment schema、artifact 路径、HTML 报告契约、QA 规则、progress 状态机、候选池入口决策 |
| P1 | 双 Agent 市场快验 | 生成两个 quick packet 和 quick gate |
| P2 | MCP 候选池 | 不依赖卖家精灵导入即可生成候选池 |
| P3 | 路线矩阵确认 | 生成 `route_matrix_confirm.json`、`data_completeness_check.json`，不进入正式深挖 |
| P4 | 双 MCP 深挖 + 冲突复核 | 生成正式 market/search evidence packet 和 conflict packet，报告不暴露冲突过程 |
| P5 | VOC 保留并接入新路线矩阵 | 生成 review_voc_package 和 voc_evidence_packet |
| P6 | 多评价 Agent | 生成 `evaluations/*.json` 和汇总 |
| P7 | 资深运营专家判断 + 报告 | 生成 integrated judgment、report_data、HTML、XLSX |
| P8 | QA 强化 | 双层强制门禁：脚本 QA（禁止术语/数据源泄漏/冲突泄漏/source_path 可解析性）+ Delivery QA Agent（强制独立 spawn、数据真实性三级交叉核对、修复循环最多 3 轮）；不可跳过、不可降级 |
| P9 | legacy 导入降级 | 手动导入不再是主流程必经入口 |

P9 legacy 退出标准：

- 连续 3 个真实 run 走 MCP 主路径并通过 QA。
- legacy fallback 回归测试仍通过。
- Skill 和文档不再把手动导入写成主路径。
- `scripts/inspect_manual_exports.py` 只作为 fallback 或历史回放入口。
- P9 后新增功能不得依赖 `import_manifest` 主路径。
- legacy 仅允许历史回放、回归测试、MCP 不可用时人工兜底。
- 删除或隐藏入口前已确认没有测试依赖主路径导入。

## 验证

修改 `packages/**`、`scripts/**`、`skills/**`、核心 `docs/**` 后必须跑：

```bash
python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir
```

推荐完整校验：

```bash
scripts/dev_verify.sh
```

若本轮生成真实 run：

```bash
python3 scripts/check_generic_redlines.py --run-dir runs/<run_id>
```

新增测试建议：

- quick packet schema 测试。
- quick gate 门控测试。
- MCP smoke call snapshot schema 测试。
- progress 状态机恢复测试。
- conflict resolver 优先级测试。
- conflict resolver 阈值测试。
- evaluation packet schema 测试。
- evaluation summary blocked / low confidence 治理测试。
- 最终 HTML 内部术语泄漏测试。
- report_data seed 到 evidence packet source_path 测试。
- 卖家精灵导入 fallback 回归测试。

## 待确认

| 问题 | 决策建议 |
|---|---|
| 卖家精灵 MCP 工具名和返回字段 | P0 smoke call 后固化 snapshot schema，未固化不得进入 P1 |
| Quick packet 和 deep packet 是否共用 schema | 共用通用结构，增加 `stage` 和 `depth` 字段 |
| 手动导入何时删除 | 主链路稳定后再删除入口；先保留 fallback |
| HTML 是否完全不展示来源 | 是；只展示判断口径和样本边界，不写来源过程 |
| 多评价 Agent 是否真实 spawn | CLI 初期允许串行执行，但 execution_provenance 必须写清 |
