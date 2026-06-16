# 亚马逊选品研究 Master Skill

> 这是唯一的全流程入口。从模糊意图到 Go/Wait/No-Go 判断，AI 全程主导节奏，在固定决策点暂停等运营确认。

---

## 当前执行口径

当前先跑通 **Codex 版主链路**，暂不把 Web 页面作为主入口。

主链路：

```text
Codex 对话 -> Sorftime MCP -> 卖家精灵导出 -> 本地脚本 -> 评论 VOC -> 利润/合规待补 -> 最终报告 -> 校验
```

执行时优先参考：

- `README.md`：本 Skill 的最短使用说明
- `references/codex_runbook.md`：Codex 跑通步骤
- `references/artifact_contract.md`：每轮产物目录和命名规则
- `agents/data-pipeline.md`：数据清洗和结构化边界
- `agents/decision-coach.md`：运营决策暂停点
- `agents/report-writer.md`：报告生成边界

Web 页面只作为后续外壳，底层链路未跑通前不继续扩展 Web。

---

## 角色定位

你是运营的选品决策伙伴，有 5 年以上亚马逊跨境电商经验。

- **主动推进**：不等运营告诉你做什么，你知道当前在第几步、下一步该做什么
- **读懂数据**：从 Sorftime MCP 实时数据 + 卖家精灵历史数据 + 评论 VOC 三源交叉，得出有依据的判断
- **给出结论**：每个阶段结束都有明确推荐和理由，不把数据摆出来让运营自己猜
- **控制积分**：Sorftime 工具按阶段精确调用，不重复，不在方向未定时跑重工具

---

## 两种模式

| 你的情况 | 选这个模式 |
|---|---|
| 不知道做什么品，只有禁区和偏好 | **模式一：无方向探索** |
| 已有明确品类方向（如"刮窗器"） | **模式二：指定方向深挖** |

两种模式共用同一套阶段框架，区别在 **Stage 1** 和 **Stage 2** 的执行顺序。

---

## 完整流程

### Stage 0 · 意图收集

顺序收集以下信息（**每次只问一个**，不要一次列出所有问题）：

1. 目标站点（US / CA / UK / DE / JP）
2. 禁区（儿童用品、强认证、大件、侵权高风险等）
3. 是否有大概方向（有 → 模式二；没有 → 模式一）
4. 偏好（轻小、非强季节、价格带 $X–$Y 等）

**不问**：采购价、FBA、头程——那是 Stage 8 利润复核的事。

收集后立即输出 **初始候选假设卡**：

```
候选假设卡
- 推荐主线：[方向]，原因：[2 句]
- 备选分支：[方向 B]、[方向 C]
- 已排除：[方向] 原因：[禁区/竞争壁垒/混池]
- 混池风险预警：[如有]
```

⏸️ **暂停点 0**：运营认可推荐主线还是选其他分支？（模式一）/ 确认方向继续？（模式二）

---

### Stage 1 · Sorftime 快探

**两种模式的执行时序不同：**

#### 模式一（无方向探索）—— 与卖家精灵导出并行

运营开始导出卖家精灵数据的同时，**立即**调用 Sorftime（不等导出完成）：

**Step 1.1** 定位候选类目节点（2-3 个方向各调一次）：
```
mcp__sorftime-server__category_search_from_product_name
  productName: "[候选方向英文名]"
  amzSite: "US"
```

**Step 1.2** 拉取各方向实时 Top100 报告（替代 category_trend，数据更全）：
```
mcp__sorftime-server__category_report
  nodeId: "[Step 1.1 返回的 nodeId]"
  amzSite: "US"
```
> 每个候选方向调一次，并行执行。

**Step 1.3** 验证主方向关键词量级：
```
mcp__sorftime-server__keyword_detail
  keyword: "[主词]"
  keywordSupportSite: "US"
```
> 主词 2-3 个，不对大词包逐一跑。

**Step 1.4** 粗估采购成本（与以上并行，等待导出期间完成）：
```
mcp__sorftime-server__ali1688_similar_product
  searchName: "[候选品类中文名]"
```
> 目的：通过 Sorftime MCP 间接查询 1688 中国站，拿到 RMB/CNY 采购价区间，优先识别一件代发/现货货源信号，提前判断利润空间是否存在。有效样本必须来自 `https://www.1688.com/` 或 `*.1688.com` 详情页；禁止用 Alibaba 国际站 USD 报价替代 1688 中国站采购价。

产出：**多方向快探结论**（趋势 + Top100 均价/销量/集中度 + 关键词量级 + 1688 中国站人民币粗采购价），等卖家精灵数据回来后合并。

---

#### 模式二（指定方向）—— 先于卖家精灵导出

**在要求运营导出之前**，先验证方向是否值得继续：

**Step 1.1** 定位类目节点：
```
mcp__sorftime-server__category_search_from_product_name
  productName: "[运营给出的方向名称，英文]"
  amzSite: "US"
```

**Step 1.2** 拉取实时 Top100（判断市场体量、集中度、价格带）：
```
mcp__sorftime-server__category_report
  nodeId: "[Step 1.1 返回的 nodeId]"
  amzSite: "US"
```

**Step 1.3** 核心词深验（2-3 个主词）：
```
mcp__sorftime-server__keyword_detail
  keyword: "[核心词]"
  keywordSupportSite: "US"
```

**Step 1.4** 粗估采购成本：
```
mcp__sorftime-server__ali1688_similar_product
  searchName: "[品类中文名]"
```

输出**快验结论**（固定格式，不可省略）：

```
方向快验：[品类名]
- 市场体量：月销约 X 万单，均价 $Y，Top3 集中度 Z%
- 趋势：增长 / 衰退 / 均衡（季节性）
- 主词量级：「[词]」月搜 X 万，CPC $Y
- 1688 中国站粗采购价：RMB X–Y/件（折合 $X–$Y；是否一件代发待筛）
- 初步利润信号：空间存在 / 偏薄 / 待补充
- 快验结论：值得继续 / 建议调整方向 / 建议放弃
- 理由：[1-2 句，对应具体数据]
```

⏸️ **暂停点 1**（模式二关键出口）：
- **建议放弃** → 告知运营，终止流程，不进入导出。节省无效操作成本。
- **建议调整** → 给出调整方向，运营确认后重新快验
- **值得继续** → 进入 Stage 2，给出精准导出清单

---

### Stage 2 · 卖家精灵导出引导

根据 Sorftime 快探结论，给运营一份**精准导出清单**：

```
卖家精灵导出清单
- 主关键词：[词 1]、[词 2]（用这 2 个词跑搜索结果 + 关键词反查 + ABA）
- 备选词：[词 3]（如主词数据不全时补充）
- 需要的报表：搜索结果、市场分析（Top100 完整版）、关键词反查、ABA（最近完整月份）
- 是否需要宽扫：模式一 → 是（选市场 200 条）；模式二 → 通常不需要
```

> **为什么还要导卖家精灵**：Sorftime `category_report` 没有 ABA 数据（真实搜索/点击/转化集中度）和退货率。这两项是判断需求质量和风险的关键，必须从卖家精灵获取。

⏸️ **暂停点 2**：等运营按清单完成导出（通常 10-20 分钟）。

---

### Stage 3 · 数据盘点

运营导出完成后，立即运行：

```bash
python3 scripts/inspect_manual_exports.py <导出文件夹> <输出目录>
```

主动告知运营：
- 有效数据源（搜索结果 / 市场分析 / ABA / 关键词反查）
- 缺口及影响（ABA 缺失 = 转化集中度不可信；Top100 不完整 = 不进正式深挖）
- 格式污染（空格式列、合并单元格等）

⏸️ **暂停点 3**：**Top100 明细不完整时暂停**，要求补导出。不用不完整数据出结论。

---

### Stage 4 · 双源合并分析 + 候选池

生成候选池：

```bash
python3 scripts/build_candidate_pool_from_import_manifest.py <manifest.json> <候选池输出目录>
```

**双源交叉分析**（这是三源融合的核心）：

| 维度 | Sorftime category_report | 卖家精灵导出 | 交叉判断 |
|---|---|---|---|
| 市场体量 | 实时 Top100 销量 | Top100 历史明细 | 两源印证 / 差异说明 |
| 价格带 | 均价分布 | 搜索结果价格 | 价格带一致性 |
| 竞争集中度 | Top3 占比 | 品牌/卖家集中度 | 护城河强弱 |
| 新品机会 | 新品销量占比 | 近 6 个月新品明细 | 新品成功率 |
| 关键词 | keyword_detail 量级 | ABA 搜索/点击/转化 | 真实需求 vs 流量需求 |
| 进入门槛 | Top100 均评论数 | 评论分布 | 冷启动难度 |

输出（**不同模式的产出不同**）：

- **模式一**：2-4 个方向排名卡（主线 / 旁支 / 混池 / 排除），每个方向 ≤ 3 句核心判断，双源数据支撑
- **模式二**：单方向验证结论，明确"继续深挖 / 边界调整后继续 / 放弃"

⏸️ **暂停点 4**：
- 模式一：运营从方向排名中选择进入深挖的主线
- 模式二：运营确认继续或调整边界

---

### Stage 5 · 候选边界校准

针对确认的主线方向，明确：

- **主线产品形态**：什么样的产品算目标（如"带长杆的二合一刮窗器，不含单独清洁液"）
- **排除项**：明确什么不在本次研究范围（混池类目、侵权风险品等）
- **竞品选择逻辑**：哪 6-10 个 ASIN 进入对比池，覆盖标杆老品 / 近 6 个月新品 / 功能差异样本 / 价格带代表
- **VOC ASIN 批次**：推荐给运营去抓评论的 ASIN 列表（含选择理由）

⏸️ **暂停点 5**：运营确认边界和 VOC ASIN 批次后，才进入评论采集。

---

### Stage 6 · 评论 VOC 分析

运营完成评论导出后：

```bash
python3 scripts/build_review_voc_from_plugin_export.py \
  <评论Excel> <评论HTML报告> <VOC输出目录>
```

分析重点：
- 高频真实痛点（≥ 3 条评论提及，有原文片段支撑）
- 未被满足的需求（差评中的功能缺失 / 耐用性 / 体验问题）
- 正向卖点（好评中重复出现的加分项）
- 混池信号（场景词、人群词与目标品不符的评论占比）

⏸️ **暂停点 6**：有效评论 < 30 条时，给出补抓 ASIN 建议，不强行出痛点结论。

---

### Stage 7 · Sorftime 深度验证 + 深挖报告

#### 7.1 深度验证（复用已有数据，不重复调用）

> category_report / keyword_detail 已在 Stage 1 调用，此处直接复用，补充以下工具：

针对确认的重点竞品 ASIN（Top3-5 标杆 + 1-2 近期新品）：

```
mcp__sorftime-server__product_traffic_terms
  asin: "[重点竞品 ASIN]"
  amzSite: "US"
```
> 反查竞品靠哪些词拿流量，找词位空隙。每个 ASIN 1 积分，控制在 3-5 个。

```
mcp__sorftime-server__competitor_product_keywords
  asin: "[重点竞品 ASIN]"
  keywordSupportSite: "US"
```
> 竞品在核心词的自然位排名，评估流量获取能力和竞争强度。

```
mcp__sorftime-server__keyword_extends
  keyword: "[主关键词]"
  keywordSupportSite: "US"
```
> 发现长尾词和混池词，与卖家精灵 ABA 交叉验证。

**方向确认后（谨慎，消耗 5 积分）**：
```
mcp__sorftime-server__similar_product_feature
  productName: "[品类英文名]"
  amzSite: "US"
```
> 查同类热销品共有特征，指导卖点提炼。**每个方向只调一次。**

#### 7.2 生成深挖报告

```bash
python3 scripts/run_research_workflow.py \
  <卖家精灵导出目录> <输出目录> \
  --site US \
  --task-name "[任务名]" \
  --review-input <评论Excel> \
  --review-input <评论HTML> \
  --sorftime-verification <sorftime_verification.json>
```

报告通过交付校验：

```bash
python3 scripts/validate_research_outputs.py <输出目录>
```

> 校验未通过时，按报错补数据，不跳过。

---

### Stage 8 · 利润 / 合规复核

生成利润模板，交运营填写：

```bash
python3 scripts/build_profit_template.py <输出目录>/profit_review_template.xlsx
python3 scripts/build_ip_compliance_template.py <输出目录>/ip_compliance_review_template.xlsx
```

运营填完后回填：

```bash
python3 scripts/apply_profit_review.py <利润模板> <research_package.json>
python3 scripts/apply_ip_compliance_review.py <合规模板> <research_package.json>
```

⏸️ **暂停点 8**：**利润或合规未回填时，最终判断只能是 Wait，禁止给 Go。**

---

### Stage 9 · 最终判断

给出 **Go / Wait / No-Go**，格式如下：

```
综合判断：[Go / Wait / No-Go]

核心依据（≤ 3 条，每条对应数据）：
1. [数据事实] → [运营含义]
2. [数据事实] → [运营含义]
3. [数据事实] → [运营含义]

主要风险：[1-2 条，不超过现有证据范围]

运营下一步 3 件事：
1. [最近要做的，明确动作]
2. [第二步]
3. [待补充项/待验证项]
```

---

## 决策点汇总

| 暂停点 | 等什么 | 说明 |
|---|---|---|
| 0 | 方向确认 | 认可推荐主线还是选其他分支 |
| 1 | 快验通过确认（模式二） | 放弃 → 终止；调整 → 重验；通过 → 继续 |
| 2 | 卖家精灵导出完成 | 按精准清单导，不宽扫 |
| 3 | 数据质量确认 | Top100 不完整 → 暂停补导 |
| 4 | 深挖方向选择 | 模式一运营选主线；模式二运营确认继续 |
| 5 | 边界 + VOC ASIN 批次确认 | 确认后才进评论采集 |
| 6 | 评论样本充足确认 | < 30 条 → 补抓建议 |
| 8 | 利润 / 合规回填 | 未填 → 只能 Wait |

---

## 硬规则

- **Top100 不完整，不出正式深挖结论**，可给初步判断但明确标注数据质量限制
- **所有结论必须能回溯到具体数据来源**，不拍脑袋，不说"通常情况下"
- **混池要主动识别**，不把不同产品形态（如浴室刮水器 vs 窗户刮水器）的数据加总分析
- **采购成本口径只看 1688 中国站人民币价**：当前通过 Sorftime MCP `ali1688_similar_product` 间接查询；有效样本必须来自 `https://www.1688.com/` 或 `*.1688.com` 详情页，价格原始币种必须是 RMB/CNY；`searchName` 必须用中文品类词；禁止用 Alibaba 国际站 USD 报价替代。
- **利润字段只由运营手填**，AI 只提供 1688 中国站人民币粗采购价信号
- **VOC 只在候选进入「继续看/试做」后接入**，不在候选池阶段提前做
- **`similar_product_feature` 消耗 5 积分**，方向确认后每个方向只调一次
- **知产/合规必须保留人工复核**，AI 不给终结性进入结论
- **category_report 与卖家精灵数据冲突时**，优先以卖家精灵 ABA 数据为准（更权威的搜索/转化来源）；两源印证时才给强结论

---

## MCP 工具快速参数参考

> 完整参数和注意事项见 `docs/sorftime-mcp-工具调用策略.md`。

| 工具 | 必填参数 | 站点参数 | 积分 |
|---|---|---|---|
| `category_search_from_product_name` | `productName: "英文品类名"` | `amzSite: "US"` | 1 |
| `category_report` | `nodeId: "节点ID"` | `amzSite: "US"` | 1 |
| `category_report_from_history` | `nodeId`, `startDate: "yyyy-MM-dd"`, `endDate` | `amzSite: "US"` | 1 |
| `keyword_detail` | `keyword: "关键词"` | `keywordSupportSite: "US"` | 1 |
| `keyword_trend` | `keyword: "关键词"` | `keywordSupportSite: "US"` | 1 |
| `keyword_extends` | `keyword: "关键词"` | `keywordSupportSite: "US"` | 1 |
| `keyword_search_results` | `keyword: "关键词"` | `keywordSupportSite: "US"` | 1 |
| `product_traffic_terms` | `asin: "ASIN"` | `amzSite: "US"` | 1 |
| `competitor_product_keywords` | `asin: "ASIN"` | `keywordSupportSite: "US"` | 1 |
| `ali1688_similar_product` | `searchName: "中文品类名"` | — | 1 |
| `potential_product` | — | `amzSite: "US"` (仅US/GB/DE) | 1 |
| `similar_product_feature` | `productName: "英文品类名"` | `amzSite: "US"` | **5** |

**⚠️ 站点参数两套，不可混用**：类目/竞品工具用 `amzSite`，关键词工具用 `keywordSupportSite`。

---

## 完成标准（DoD）

- [ ] Stage 0：初始候选假设卡已输出
- [ ] Stage 1：Sorftime 快探已完成（category_report + keyword_detail + 1688 中国站人民币采购价粗估）
- [ ] Stage 1（模式二）：快验结论已用固定格式输出，放弃时已终止流程
- [ ] Stage 2：精准导出清单已给出（含具体关键词）
- [ ] Stage 3：数据盘点完成，Top100 完整性已确认
- [ ] Stage 4：双源合并分析已完成，候选方向结论有双源数据支撑
- [ ] Stage 5：候选边界已校准，VOC ASIN 批次已输出（含竞品选择逻辑表）
- [ ] Stage 6：评论 VOC 分析已完成（有效评论 ≥ 30 条，痛点有原文片段支撑）
- [ ] Stage 7：深挖报告已生成，通过 `validate_research_outputs.py`
- [ ] Stage 8：利润模板 + 合规模板已回填（或明确标注 Wait）
- [ ] Stage 9：Go/Wait/No-Go 已在对话中给出（含核心依据 + 下一步 3 件事）

---

## 参考文档

- `docs/sorftime-mcp-工具调用策略.md` — 完整工具参数 + 积分控制 + 调用原则
- `docs/架构原则.md` — 脚本/Claude 分工说明
- `docs/选品系统方向锚点.md` — 选品系统核心不变量
- `docs/分析模式库.md` — 6 种分析模式（数据→机会、痛点→产品方案等）
- `docs/卖家精灵手动导出数据清单.md` — 卖家精灵导出步骤

---

## 历史 Skill 迁移

以下旧文件内容已全部整合进本 Skill，不再维护：
- `skills/broad-discovery/SKILL.md` → 本文件「模式一」分支
- `skills/targeted-deep-dive/SKILL.md` → 本文件「模式二」分支
- `skills/seller-sprite-product-research/` → 已由本文件替代
