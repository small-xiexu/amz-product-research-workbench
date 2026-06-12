# AI 交互式选品流程引擎

主体验不是一键生成报告，而是 AI 和运营逐步完成选品。最终仍生成正式报告，但报告来自交互过程中的证据、决策、暂停点、待补项和最终判断。

## 两种模式

| 模式 | 入口 | AI 主任务 | 运营参与点 |
|---|---|---|---|
| 无方向探索 | 模糊意图，如“美国站家居清洁小工具” | 拆方向、扫类目、收窄候选 | 选主线、确认排除项、导出大盘数据 |
| 指定方向深挖 | 明确方向，如“窗户刮水器二合一工具” | 验证市场、竞品、VOC、利润、合规 | 确认边界、上传数据、抓评论、补利润/合规 |

## 核心数据

| 对象 | 作用 | 产物 |
|---|---|---|
| `workflow_state` | 当前流程状态：阶段、已有数据、缺失数据、是否需要运营决策、下一步动作 | `workflow_state.json` |
| `decision_log` | 关键决策记录：谁确认了什么、为什么、依据是什么 | `decision_log.json` |
| `next_action_card` | AI 当前给运营的下一步动作卡 | 对话输出 / JSON |
| `research_package` | 重点候选的结构化深挖数据 | `research_package.json` |
| `final_report` | 最终正式报告 | `report.md` / `dashboard.html` / `data.xlsx` |

最终报告读取：

```text
research_package.json
+ workflow_state.json
+ decision_log.json
+ evidence_refs
```

## 阶段状态机

| 阶段 | AI 负责 | 可用工具 | 何时暂停 |
|---|---|---|---|
| `intent_intake` | 理解运营意图，识别模式 | 无 | 方向过宽或边界不清 |
| `exploration_planning` | 拆 2-4 个方向，判断先调 MCP 还是先导出 | Sorftime broad/category | 需要运营选主线 |
| `seller_sprite_request` | 给卖家精灵导出清单、关键词、类目、文件要求 | 无 | 等运营导入文件 |
| `data_inventory` | 盘点导出文件、缺失项、混池风险 | 本地导入脚本 | 数据缺失或混池严重 |
| `candidate_pool_review` | 生成候选池预审，解释候选来源 | 候选池脚本 / Sorftime 验证 | 需要运营选深挖候选 |
| `boundary_confirmation` | 明确主线、保留参考、排除项 | 无 | 运营未确认边界 |
| `voc_batch_planning` | 给评论抓取 ASIN 批次 | 候选池数据 | 等运营爬评论 |
| `voc_analysis` | 读取评论，归纳痛点/亮点/机会 | 评论导入脚本 | 评论样本不足 |
| `deep_dive` | 综合市场、竞品、VOC、MCP | Sorftime 深调 / 报告底表 | 产品边界或证据不足 |
| `profit_compliance_review` | 生成利润/合规模板和待补项 | 模板脚本 | 等运营补利润/合规 |
| `final_decision` | 输出 Go/Wait/No-Go 和下一步动作 | 报告渲染器 | 缺关键项只能 Wait |

## MCP 调用规则

| 场景 | 动作 |
|---|---|
| 只有模糊方向 | 可调用 Sorftime broad/category，辅助拆方向 |
| 已有 2-4 个候选方向 | 调类目趋势、关键词趋势，决定优先验证线 |
| 已导入卖家精灵数据 | 调 MCP 做趋势、关键词、竞品流量词交叉验证 |
| 候选边界混乱 | 先问运营确认，不深调 MCP |
| 进入重点候选深挖 | 调竞品流量词、相似品、潜力品 |
| 缺 Top100 明细 | 不用 MCP 硬补，要求运营导出卖家精灵 Top100 |

## 卖家精灵导出触发规则

| 场景 | AI 指令 |
|---|---|
| 无方向探索 | 让运营导出“选市场 200 条”或大类目市场数据 |
| 指定方向深挖 | 给 2-3 个主关键词 + 1 个备选词，要求导出搜索结果、市场分析、关键词反查 |
| 缺 Top100 明细 | 暂停正式深挖，要求补导出 |
| 数据混池严重 | 解释混池词和排除规则，要求按更窄关键词重导 |
| 需求判断不足 | 建议补 ABA / 关键词趋势数据 |

## 评论 VOC 触发规则

| 场景 | AI 指令 |
|---|---|
| 候选池未确认主线 | 不给 ASIN，先让运营确认边界 |
| 主线已确认 | 给 ASIN 批次：量级标杆、新品、差评高发、功能差异、价格带代表 |
| 竞品池太杂 | 先解释杂在哪里，要求确认排除规则 |
| 评论样本不足 | 指定补抓 ASIN，不写强痛点结论 |
| 评论已导入 | 基于评论证据输出痛点、亮点、改品机会和证据引用 |

## 运营决策点

必须暂停并让运营确认：

1. 初始方向主线
2. 排除规则和混池边界
3. 哪个候选进入深挖
4. 评论抓取 ASIN 批次
5. 评论样本是否足够
6. 是否补利润和合规模板
7. 最终继续验证、打样、观察或放弃

## 下一步动作卡

AI 每次推进后输出一个动作卡：

```json
{
  "stage": "candidate_pool_review",
  "decision_required": true,
  "question": "请选择本轮要进入深挖的候选方向。",
  "recommended_action": {
    "type": "operator_decision",
    "label": "确认深挖候选",
    "reason": "候选池已有 3 个方向，但边界和资源投入不同。"
  },
  "options": [
    {
      "id": "deep_dive_mainline",
      "label": "深挖主线候选",
      "impact": "进入 VOC ASIN 批次规划和深挖报告。"
    },
    {
      "id": "refine_boundary",
      "label": "先修正边界",
      "impact": "更新排除项后重新生成候选池。"
    }
  ],
  "evidence_refs": [
    "candidate_pool.json",
    "precheck_data.xlsx"
  ]
}
```

## 最终报告变化

正式报告保留 P20 固定 12 章结构，不额外拆新章；交互过程沉淀在两处：

- `数据来源与口径`：展示 `workflow_state` 的当前阶段、模式、初始意图、是否等待运营决策、当前问题和状态来源文件。
- `下一步动作与证据附录`：展示 `next_action_card` 和 `decision_log`，让运营能回看 AI 为什么暂停、让谁做了什么决策、证据来自哪里。

`data.xlsx` 新增 `交互决策记录` Sheet。

| 报告内容 | 数据来源 |
|---|---|
| 运营原始意图 | `workflow_state.initial_intent` |
| AI 初始假设 | `decision_log` |
| 运营确认主线 | `decision_log` |
| 导出数据范围 | `workflow_state.known_inputs` |
| 候选筛选理由 | `candidate_pool` |
| VOC ASIN 选择理由 | `workflow_state.next_actions` / `candidate_pool.next_review_voc_asins` |
| 利润/合规待补 | `research_package` / `workflow_state.missing_inputs` |
| 最终 Go/Wait/No-Go | `research_package.decision_review` + `decision_log` |

## 现有一键流程定位

`scripts/run_research_workflow.py` 保留，但定位为：

- 开发回归
- 数据齐全后重跑报告
- 同一批数据重新渲染
- 批量验证报告输出

主产品体验使用 `interactive_workflow`，不是一键跑到底。

如果要把交互过程写进最终报告，批量重跑入口需要传入当前 `workflow_state.json`：

```bash
python3 scripts/run_research_workflow.py \
  <卖家精灵导出文件夹> \
  <输出目录> \
  --site US \
  --task-name <任务名> \
  --workflow-state /tmp/workflow_state.json
```
