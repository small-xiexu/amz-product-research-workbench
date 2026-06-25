# P5 VOC Gate 契约说明

更新日期：2026-06-24

本文件定义 CLI 双 MCP 多 Agent 流程中 `stage_7_voc_gate` 阶段的所有输入、输出、Schema 候选字段、Gate 决策规则、阻断条件、样本阈值、progress 规则和范围边界。P5-1 / P5-2 / P5-3 / P5-4 实现时必须遵守本契约。

## 1. 阶段定位

`stage_7_voc_gate` 是 P4 `stage_6_deep_dive` 完成后的评论 VOC 阶段。它承接双 MCP 深挖结果，在进入 Stage 7 正式报告前完成 VOC 证据包生成和 Gate 决策。

```
P4 stage_6_deep_dive (done)
  → stage_7_voc_gate (P5)
    → P5-1: ASIN 批次计划
    → P5-2: 评论导入与规范化
    → P5-3: VOC Evidence Packet + Gate 决策
  → stage_7_report (待实现，不进入 P5)
```

## 2. 输入清单

| # | 路径 | 来源 | 用途 |
|---|---|---|---|
| 1 | `runs/<run_id>/route_matrix_confirm.json` | P3 | 路线配置、selected_routes、ASIN 角色映射 |
| 2 | `runs/<run_id>/candidate_pool.json` | P2 | 候选池 ASIN、候选类目、竞品身份 |
| 3 | `runs/<run_id>/market_structure/market_structure_evidence_packet.json` | P4-2 | 卖家精灵市场结构证据、参考 ASIN 池 |
| 4 | `runs/<run_id>/search_demand/search_demand_evidence_packet.json` | P4-3 | Sorftime 搜索需求证据、类目 Top100 ASIN |
| 5 | `runs/<run_id>/conflict_review/deep_data_completeness_check.json` | P4-4 | 数据完整性水平、阻断缺口 |
| 6 | `runs/<run_id>/conflict_review/conflict_resolution_packet.json` | P4-4 | 冲突水平（none/warning/blocker）、冲突明细 |
| 7 | 评论插件导出的 `.xlsx` / `.html` / `.json` 文件 | 运营手动导出 | P5-2 评论原始数据 |

## 3. 输出清单

| # | 路径 | 阶段 | 说明 |
|---|---|---|---|
| 1 | `runs/<run_id>/review_voc/review_asin_batch.json` | P5-1 | VOC ASIN 批次计划，告诉运营应抓哪些 ASIN 的评论 |
| 2 | `runs/<run_id>/review_voc/review_voc_package.json` | P5-2 | 规范化评论数据包（纯数据层，无痛点分析） |
| 3 | `runs/<run_id>/review_voc/voc_evidence_packet.json` | P5-3 | VOC 证据包，含痛点归因、正向驱动、规格映射 |
| 4 | `runs/<run_id>/review_voc/voc_gate.json` | P5-3 | VOC Gate 决策（continue/watch/stop/need_more_reviews） |
| 5 | `runs/<run_id>/progress.json`（更新） | P5-3 | stage_7_voc_gate 状态推进 |

## 4. Schema 候选字段

### 4.1 review_asin_batch.json

```json
{
  "schema_version": "p5-voc-gate-v1",
  "batch_id": "review_asin_batch",
  "run_id": "<run_id>",
  "generated_at": "<ISO8601>",
  "source_route_matrix": "route_matrix_confirm.json",
  "source_candidate_pool": "candidate_pool.json",
  "source_evidence_packets": [
    "market_structure/market_structure_evidence_packet.json",
    "search_demand/search_demand_evidence_packet.json"
  ],
  "site": "US",
  "asin_items": [
    {
      "asin": "<ASIN>",
      "route_ref": "<路线标识>",
      "asin_role": "primary_reference | high_sales_benchmark | new_release_sample | premium_benchmark | painpoint_reference | excluded_reference",
      "selection_reason": "<为什么选这个 ASIN 采评论>",
      "source": "seller_sprite | sorftime | candidate_pool",
      "is_primary_route": true,
      "is_mixed_pool_control": false
    }
  ],
  "route_coverage": [
    {
      "route_ref": "<路线标识>",
      "asin_count": 3,
      "roles_covered": ["primary_reference", "high_sales_benchmark", "new_release_sample"],
      "missing_roles": ["premium_benchmark"]
    }
  ],
  "operator_instruction": {
    "site": "US",
    "entry_point": "评论慢速采集助手",
    "put_dir": "<绝对路径>",
    "file_naming": "<站点>_review_voc_<批次>_<日期>.xlsx",
    "import_command": "python3 scripts/build_review_voc_package.py <run_dir> <export_files>"
  },
  "data_gaps": [],
  "evidence_refs": []
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `"p5-voc-gate-v1"` |
| `batch_id` | 是 | 固定 `"review_asin_batch"` |
| `run_id` | 是 | 与 run 目录名一致 |
| `asin_items[]` | 是 | 至少 1 个 ASIN |
| `asin_items[].asin` | 是 | ASIN 码 |
| `asin_items[].route_ref` | 是 | 所属产品路线 |
| `asin_items[].asin_role` | 是 | 见 ASIN 角色枚举 |
| `asin_items[].selection_reason` | 是 | 选择理由 |
| `asin_items[].source` | 是 | `seller_sprite` / `sorftime` / `candidate_pool` |
| `route_coverage[]` | 是 | 每条路线的 ASIN 覆盖情况 |
| `operator_instruction` | 是 | 给运营的采集指令 |
| `data_gaps` | 是 | ASIN 选择中的缺口 |

**ASIN 角色枚举：**

| 角色 | 用途 |
|---|---|
| `primary_reference` | 主推路线最相似竞品 |
| `high_sales_benchmark` | 高销量标杆 |
| `new_release_sample` | 新品或低评论仍有销量样本 |
| `premium_benchmark` | 高客单或升级款样本 |
| `painpoint_reference` | 评分偏低或差评集中的样本 |
| `excluded_reference` | 混池/旁支对照 |

### 4.2 review_voc_package.json

复用并扩展现有 `build_review_voc_from_plugin_export.py` 的 `build_voc_package()` 输出结构。P5-2 改造时保持向后兼容。

```json
{
  "schema_version": "p5-voc-gate-v1",
  "metadata": {
    "package_id": "review-voc-<timestamp>",
    "generated_at": "<ISO8601>",
    "source_type": "review_plugin_export",
    "run_id": "<run_id>",
    "source_files": ["<文件名>"],
    "source_batch_ref": "review_voc/review_asin_batch.json",
    "integration_note": "Excel is the structured source of truth; HTML AI reports are auxiliary reading references.",
    "analysis_note": "痛点/亮点/改品机会分析由 VOC Evidence Agent 基于 normalized_reviews 完成，脚本只做数据提取和规范化。"
  },
  "stats": {
    "review_count": 150,
    "asin_count": 8,
    "asins": ["<ASIN>"],
    "date_range": {"start": "2025-01-01", "end": "2026-06-01"},
    "rating_distribution": {"5星": 60, "4星": 30, "3星": 20, "2星": 20, "1星": 20},
    "sentiment_distribution": {"正面": 90, "中性": 20, "负面": 40},
    "low_rating_count": 40,
    "verified_count": 120,
    "media_review_count": 25,
    "entry_site_distribution": [{"name": "US", "count": 150}],
    "review_region_distribution": [{"name": "US", "count": 145}],
    "primary_entry_site": "US",
    "primary_review_region": "US",
    "source_scope_note": "站点字段表示评论采集入口，不等同于目标市场；评论地区表示评论样本实际地区。"
  },
  "ai_report_reference": {
    "source_files": [],
    "text_excerpt": "",
    "usage": "仅作辅助阅读，不作为可追溯证据主来源。"
  },
  "normalized_reviews": [
    {
      "review_id": "<ID>",
      "asin": "<ASIN>",
      "site": "US",
      "review_region": "US",
      "raw_date": "2026-01-15",
      "review_date": "2026-01-15",
      "raw_rating": "2",
      "rating": 2.0,
      "sentiment": "负面",
      "author": "<author>",
      "verified": "是",
      "helpful_count": 5,
      "has_buyer_image": "否",
      "image_count": 0,
      "has_video": "否",
      "variant": "ColorA-SizeM",
      "color": "ColorA",
      "size": "SizeM",
      "review_text": "The product broke after two weeks...",
      "review_text_zh": "产品两周后就坏了...",
      "url": "https://...",
      "source_file": "<文件名>"
    }
  ],
  "data_gaps": [],
  "summary": {},
  "pain_points": [],
  "highlights": [],
  "opportunity_hypotheses": []
}
```

**与旧版差异：**
- 新增 `schema_version`、`metadata.run_id`、`metadata.source_batch_ref`
- 新增 `stats.verified_count`（验证购买数）
- 新增 `data_gaps` 顶层字段
- `summary`、`pain_points`、`highlights`、`opportunity_hypotheses` 保持为空数组/空对象（兼容旧字段，但 P5 脚本不填充）

### 4.3 voc_evidence_packet.json

VOC Evidence Agent 的输出，遵循 `skills/amazon-product-research/references/evidence_packet_contract.md` 通用结构：

```json
{
  "packet_id": "voc_evidence",
  "packet_version": "p5-voc-gate-v1",
  "run_id": "<run_id>",
  "agent_role": "VOC Evidence Agent",
  "source_scope": ["review_plugin_export"],
  "created_at": "<ISO8601>",
  "input_refs": [
    {"type": "file", "path": "review_voc/review_voc_package.json"},
    {"type": "file", "path": "review_voc/review_asin_batch.json"},
    {"type": "file", "path": "conflict_review/conflict_resolution_packet.json"}
  ],
  "execution_provenance": {
    "executed_by_agent": true,
    "agent_role": "VOC Evidence Agent",
    "execution_mode": "real_subagent_spawn",
    "subagent_id": "",
    "note": ""
  },
  "route_refs": ["<路线标识>"],
  "review_scope": {
    "total_reviews": 150,
    "total_asins": 8,
    "low_rating_count": 40,
    "date_range": {"start": "2025-01-01", "end": "2026-06-01"},
    "site": "US",
    "review_region_primary": "US"
  },
  "asin_coverage": {
    "covered_routes": 3,
    "total_routes": 3,
    "by_route": [
      {
        "route_ref": "<路线标识>",
        "asin_count": 4,
        "review_count": 80,
        "low_rating_count": 22,
        "meets_minimum_threshold": true
      }
    ],
    "by_asin_role": {
      "primary_reference": {"asin_count": 2, "review_count": 60},
      "high_sales_benchmark": {"asin_count": 1, "review_count": 300},
      "new_release_sample": {"asin_count": 1, "review_count": 5},
      "painpoint_reference": {"asin_count": 1, "review_count": 80}
    },
    "uncovered_roles": ["premium_benchmark"]
  },
  "pain_points_by_dimension": [
    {
      "dimension": "durability",
      "severity": "P0",
      "frequency": 15,
      "description": "产品在正常使用中结构损坏",
      "evidence_quotes": ["原文片段1", "原文片段2"],
      "evidence_refs": [
        {
          "review_id": "<ID>",
          "asin": "<ASIN>",
          "rating": 1.0,
          "quote": "原文片段",
          "source_path": "review_voc/review_voc_package.json#normalized_reviews[3]"
        }
      ],
      "spec_requirement": "连接处需通过XX次循环测试",
      "sample_tests": ["循环疲劳测试"],
      "listing_risk_note": "如不解决，退货率可能超过X%"
    }
  ],
  "unmet_needs": [
    {
      "need": "更强的XX性能",
      "frequency": 8,
      "description": "多位用户提到现有产品无法满足XX场景",
      "evidence_refs": []
    }
  ],
  "differentiation_opportunities": [
    {
      "opportunity": "增加XX配件提升使用便利性",
      "driver": "好评中反复出现的加分项",
      "evidence_refs": []
    }
  ],
  "mixed_pool_signals": [
    {
      "signal": "部分评论描述的使用场景与目标路线不符",
      "affected_review_count": 5,
      "assessment": "占比低，不影响主路线结论"
    }
  ],
  "review_quality_gaps": [
    {
      "gap_type": "low_review_count",
      "route_ref": "<路线标识>",
      "description": "新品样本仅有5条评论，不足以判断该路线的VOC",
      "recommended_action": "补抓该路线2-3个新品ASIN的评论"
    }
  ],
  "confidence": "medium",
  "data_gaps": [],
  "evidence_refs": [],
  "lineage": []
}
```

### 4.4 voc_gate.json

```json
{
  "schema_version": "p5-voc-gate-v1",
  "gate_id": "voc_gate",
  "run_id": "<run_id>",
  "generated_at": "<ISO8601>",
  "input_refs": [
    "review_voc/voc_evidence_packet.json",
    "review_voc/review_voc_package.json",
    "review_voc/review_asin_batch.json",
    "conflict_review/conflict_resolution_packet.json"
  ],
  "decision": "continue | watch | stop | need_more_reviews",
  "decision_reason": "<2-3句话说明为什么给出这个决策>",
  "inherited_warnings": [
    {
      "source": "conflict_resolution_packet",
      "level": "warning",
      "description": "P4 冲突复核为 warning，VOC Gate 继承此警告"
    }
  ],
  "blockers": [],
  "checks": {
    "p4_conflict_level": "none",
    "min_review_threshold_met": true,
    "low_rating_threshold_met": true,
    "route_coverage_complete": true,
    "asin_role_coverage_complete": false,
    "mixed_pool_separated": true
  },
  "thresholds": {
    "min_total_reviews": 30,
    "min_low_rating_reviews": 10,
    "current_total_reviews": 150,
    "current_low_rating_reviews": 40
  },
  "required_next_actions": [
    "补抓 premium_benchmark 角色的 ASIN 评论",
    "人工复核 P4 conflict warning 中的价格带冲突"
  ],
  "evidence_refs": [
    "review_voc/voc_evidence_packet.json",
    "conflict_review/conflict_resolution_packet.json"
  ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定 `"p5-voc-gate-v1"` |
| `decision` | 是 | `continue` / `watch` / `stop` / `need_more_reviews` |
| `decision_reason` | 是 | 决策依据 |
| `inherited_warnings[]` | 是 | 从 P4 conflict resolution 继承的警告 |
| `blockers[]` | 是 | 阻断继续的原因 |
| `checks` | 是 | 各项检查结果 |
| `thresholds` | 是 | 样本阈值及当前值 |
| `required_next_actions[]` | 是 | 下一步动作 |

## 5. Gate 决策规则

### 5.1 决策枚举

| 决策 | 含义 | 触发条件示例 |
|---|---|---|
| `continue` | VOC 证据充分，可进入 Stage 7 报告 | 评论 >= 30，低分 >= 10，路线覆盖完整，P4 无 blocker |
| `watch` | 可继续但有警告，Stage 7 报告中需标注风险 | 评论 >= 30 但某路线覆盖不足，或 P4 conflict warning |
| `stop` | 不应继续，VOC 揭示方向性问题 | 核心路线大量差评指向不可解决的痛点，或 P4 conflict blocker |
| `need_more_reviews` | 评论样本不足，需补抓 | 有效评论 < 30 条，或低分评论 < 10 条 |

### 5.2 阻断条件

以下条件满足任一项时，Gate 不得输出 `continue`：

1. **P4 conflict blocker**：`conflict_resolution_packet.conflict_level == "blocker"` → 至少输出 `stop` 或 `watch`，且 `blockers[]` 必须包含冲突详情。
2. **P4 completeness blocker**：`deep_data_completeness_check.completeness_level == "blocker"` → 不生成 Gate，直接阻断。
3. **评论样本不足**：有效评论 < 30 条 → `need_more_reviews`，`required_next_actions` 给补抓 ASIN 清单。
4. **低分评论不足**：低分评论（<=3星）< 10 条 → 至少 `watch`，标注低分样本不足。
5. **核心路线无覆盖**：主推路线在任何 ASIN 都没有评论 → `need_more_reviews`，指定需要补抓的 ASIN。
6. **评论导出文件缺失**：没有任何评论插件导出文件 → 阻断，不生成 Gate。

### 5.3 P4 警告继承

若 `conflict_resolution_packet.conflict_level == "warning"`：
- `voc_gate.inherited_warnings[]` 必须包含该警告。
- Gate 决策可仍为 `continue`，但 `required_next_actions` 必须提示人工复核冲突项。
- 若 Gate 决策本身也有问题（如样本不足），两者叠加可能导致 `watch` 或 `need_more_reviews`。

### 5.4 样本阈值

| 指标 | 阈值 | 不满足时 |
|---|---|---|
| 有效评论总数 | >= 30 | `need_more_reviews` |
| 低分评论数（<=3星） | >= 10 | 至少 `watch` |
| 主推路线覆盖 | 每条至少 1 个 ASIN 有评论 | 标注缺失路线 |
| mixed_pool 分离 | 混池/排除样本评论不与主推路线混算 | 若混算，gate 必须标为数据质量问题 |

## 6. Progress 规则

### 6.1 stage_7_voc_gate 状态流转

```
P4-4 完成时:
  stages.stage_6_deep_dive.status = "done"
  stages.stage_7_voc_gate.status = "pending"
  next_action = { stage_id: "stage_7_voc_gate", type: "generate_asin_batch", description: "..." }

P5-1 完成时 (review_asin_batch.json 生成):
  stages.stage_7_voc_gate.status = "running"
  next_action = { stage_id: "stage_7_voc_gate", type: "wait_operator_export", description: "等待运营按 ASIN 清单完成评论导出" }

P5-2 完成时 (review_voc_package.json 生成):
  stages.stage_7_voc_gate.status = "running"
  next_action = { stage_id: "stage_7_voc_gate", type: "generate_voc_evidence", description: "..." }

P5-3 完成时 (voc_gate.json 生成):
  stages.stage_7_voc_gate.status = "done"
  // 根据 gate decision:
  // continue → next_action = { stage_id: "stage_7_report", ... }
  // watch → next_action = { stage_id: "stage_7_report", type: "with_warnings", ... }
  // stop → next_action = { type: "stop", ... }，不推进 stage_7_report
  // need_more_reviews → next_action = { type: "need_more_reviews", stage_id: "stage_7_voc_gate", ... }
```

### 6.2 completed_artifacts 累积

P5 各阶段完成后追加：
- P5-1：`"review_voc/review_asin_batch.json"`
- P5-2：`"review_voc/review_voc_package.json"`
- P5-3：`"review_voc/voc_evidence_packet.json"`、`"review_voc/voc_gate.json"`

## 7. 与 P4 conflict_review 的关系

```
P4 conflict_resolution_packet
  │
  ├─ conflict_level == "none"
  │   └─ P5-3: voc_gate 正常决策，无继承警告
  │
  ├─ conflict_level == "warning"
  │   └─ P5-3: voc_gate 继承 warning，required_next_actions 提示人工复核
  │       Gate 可仍为 continue，但必须带 inherited_warnings
  │
  └─ conflict_level == "blocker"
      └─ P5-3: voc_gate 不得输出 continue
          blockers[] 必须包含冲突详情
          至少输出 watch 或 stop
          若评论样本也不足 → stop
```

P5 不重新计算或覆写 P4 的冲突结论。P4 的 `conflict_level` 是 P5 的只读输入。

## 8. 范围边界（P5 不做什么）

- 不生成正式报告、HTML、XLSX。
- 不进入评价 Agent 最终判断或资深运营专家最终排序。
- 不进入供应商、成本、利润、合规、产品方案。
- 不改 Web / server 主链路。
- 不写死任何具体品类、ASIN、关键词、品牌、卖家、供应商或价格。
- VOC 脚本不写关键词规则做痛点分析。痛点归因由 VOC Evidence Agent 基于 `normalized_reviews` 和 `evidence_refs` 生成。
- 不实现 `stage_7_report`。`voc_gate` 的 `next_action` 可指向 `stage_7_report`，但不进入其实现。

## 9. 通用性红线

- 所有 Schema、Contract、Pipeline、CLI、Agent prompt 和测试不得出现具体品类名、ASIN、关键词、品牌、卖家或供应商。
- 测试 fixture 只能用 `<generic_*>` 占位符。
- 每次修改通用文件后必须运行 `python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir`。

## 10. 现有资产复用说明

| 现有资产 | P5 用途 | 改造程度 |
|---|---|---|
| `packages/research_core/pipeline/build_review_voc_from_plugin_export.py` | P5-2 数据读取与规范化核心逻辑 | 改造为 pipeline 模块（函数可被程序调用），保留 CLI 入口 |
| `packages/research_core/contracts/validators.py` `validate_review_voc_package()` | P5-2 输出契约校验 | 扩展字段校验（新增 schema_version、run_id 等） |
| `skills/amazon-product-research/agents/voc-evidence-agent.md` | P5-3 VOC Evidence Agent 角色定义 | 无需改造，作为 Agent prompt 使用 |
| `docs/评论VOC导出指令完整性规范.md` | P5-1 运营指令输出格式 | 复用 ASIN 输出格式，P5-1 的 operator_instruction 参照此规范 |
| `skills/amazon-product-research/references/evidence_packet_contract.md` | P5-3 voc_evidence_packet 结构 | 遵循通用 Evidence Packet 结构 |
