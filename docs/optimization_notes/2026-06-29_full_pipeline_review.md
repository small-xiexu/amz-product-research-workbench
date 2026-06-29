# 全流程复盘：吊扇活性炭过滤棉片 13 Stage 实战感受

2026-06-29，完整跑完 `20260629_吊扇活性炭过滤棉片` 全部 13 个阶段，US 站点，双路线（standard-carbon-filter + premium-zeolite-filter），最终判断 watch，QA Round 2 PASS。

---

## 整体感受

### 做得好的

- **双源交叉验证很有价值**。卖家精灵看市场结构、Sorftime 看搜索需求，两个视角拼在一起才有了"主类目严重混池但纯 filter 市场真实存在"这个关键判断。单源做不到。
- **并行 Agent 设计合理**。Stage 2、6、9 的并行 spawn 没有互相阻塞，节奏紧凑。尤其是 6 个 Evaluation Agent 同时跑，几分钟出完整评价矩阵。
- **VOC 分析是真正的差异化引擎**。附着性问题、除臭效果衰减这些痛点是从评论原文里挖出来的，不是看类目数据能猜到的。这是整个流程最有"运营感"的环节。

### 不足的

- **契约校验的性价比偏低**。每个 Stage 都要跑校验脚本 → 打回修复 → 再校验，但大量校验失败是字段缺失、命名不对、占位符扫描误报这类机械问题，不是分析质量问题。像是在帮 Agent 做格式校对，而不是做真正的质量把控。
- **Stage 10a/10b 三段式太重**。脚本生成骨架 → 两个 Agent 填 9 字段 → Lead Operator 再交叉验证，读的是同一批数据，三层过手。实际观察 Route Strategy 和 Growth & Risk 的产出有重叠，Lead Operator 的"交叉验证"也没发现前两个 Agent 没发现的新问题。合并成两步完全够。
- **source_path 全链路溯源是理想主义**。从 MCP 快照到 HTML 最终报告，中间经过 5-6 道转换，要求每一步都带着溯源路径。目标是对的，但当前实现方式是把负担全部压在最后两个 Agent 身上，前面几道工序只管消费数据不管保留来源。链条的设计方向和执行方向是反的。
- **13 Stage 的停顿点设计让流程偏线性**。Agent 内部可以并行，但 Stage 之间串行，每个 Stage 都有校验 → 更新 progress → 才能进下一步。实际人机交互的暂停点只有意图确认、方向确认、候选池确认、路线确认、评论导出这 5 个。剩下 8 个 Stage 的停顿是"等校验通过"的系统等待，不是运营决策点。这些系统等待如果能让主 Agent 自动流转会更顺畅。

### 一句话

这套流程能产出有依据的市场判断，但契约层和溯源层的设计偏防御性，把简单问题复杂化了。如果能去掉一些"为校验而校验"的环节、合并重叠的 Agent 角色，同样的分析质量可以用更少的步骤跑完。

---

## 具体痛点

### 1. source_path 溯源链是最脆弱的环节

**Why:** QA Round 1 的 5 条阻断中 4 条与 source_path 有关。数据流经多道工序后溯源断裂：`证据包(MCP快照) → seed抽取 → report_data增强 → HTML渲染`，每过一道 source_path 就丢一层。到 report_data 时 37% 的路径变成了 `__ai_judgment__`，只能人工逐条补。

**How to apply:** `build_report_seed.py` 抽取数据时应原样携带证据包的 source_path，不让 Report Generation Agent 事后反查。seed 脚本离证据包最近，它做溯源成本最低。

---

### 2. 脚本 QA 的 values_consistent 检查误报率高

**Why:** 17 条 mismatches 全部是 `"16,236 units（含混池品，纯 filter 约 12K）"` vs `16236` 这种——report_data 做了运营可读性增强，脚本拿增强后的文本去和原始数值做精确比对，必然不匹配。

**How to apply:** 脚本 QA 应只比对裸数值字段（price、monthly_sales、rating 等），跳过已做文本增强的字段。或在 seed 阶段把 raw_value 和 display_value 分开存储，QA 只比对 raw_value。

---

### 3. 占位符扫描过于粗暴

**Why:** `build_mcp_candidate_pool.py` 的占位符扫描把 `"source": "sellersprite"` 这类合法元数据字段也标记为内部术语泄漏。扫描逻辑是全文字符串匹配 `sellersprite|sorftime|mcp|quick_gate|workflow_state`，没有区分"数据来源声明"和"未填充占位符"。

**How to apply:** 扫描时排除已知的元数据字段名（source、data_source、source_refs），或改为只扫描值域而非键名。

---

### 4. route_matrix_confirm.json 的 route_matrix 字段是陷阱

**Why:** 字段设为空数组 `[]`，但 Agent 容易写成字符串 `"same_as_route_options"`——导致下游 `build_analysis_packet.py`（line 463）和 `build_report_seed.py` 连续崩溃。两次踩同一个坑。

**How to apply:** `build_route_matrix_confirm.py` 校验时加类型检查，非数组直接阻断并给出明确错误信息。或在 schema 中去掉这个冗余字段（信息已在 route_options 中）。

---

### 5. Stage 6 深挖的非头部竞品数据缺失是系统性 gap

**Why:** BioStrike、Tuanse、Niifawh 的月销数据始终是 null。不是 Agent 没查——是 MCP 工具对这些低销量 ASIN 本身就不返回销量。但整个流程没有在 Stage 6 明确标注"哪些数据 MCP 无法提供"，而是把 null 一路传递到 Stage 9 评价和 Stage 12 报告，下游反复尝试。

**How to apply:** Stage 6 的 evidence packet 中加 `data_unavailable` 字段，显式列出"已尝试获取但 MCP 无数据"的指标。下游 Agent 看到这个字段就知道不是漏查，避免反复尝试。

---

### 6. Stage 8 VOC 的 ASIN 角色覆盖不够智能

**Why:** `review_asin_batch.json` 中 15 个 ASIN 的 asin_role 只覆盖了 high_sales_benchmark 和 target_price_band_sample，缺少 painpoint_reference 和 primary_reference。不是采集量不够——是 ASIN 选择策略没有优先覆盖 VOC 分析最需要的角色。

**How to apply:** `build_review_asin_batch.py` 在选 ASIN 时优先确保每条路线至少覆盖 primary_reference + painpoint_reference 两个角色，再补充其他。

---

### 7. Stage 10a/10b 三段式判断链路偏重

**Why:** 脚本生成骨架 → Route Strategy + Growth & Risk 并行填 9 字段 → Lead Operator 交叉验证 + 拍板。三步两个 spawn。Route Strategy 和 Growth & Risk 的产出有相当多重叠，Lead Operator 再读一遍同样的数据做交叉验证。

**How to apply:** 考虑合并为两段——Route Strategy + Growth & Risk 并行产出后，主 Agent 直接做交叉验证和拍板。主 Agent 本身就应该是"资深运营"，交叉验证和 final_verdict 判断完全能做，不需要单独的 Lead Operator Agent spawn。

---

## 优先级

1. **#1 source_path 携带** — 直接决定 Stage 13 QA 能否一轮过
2. **#2 QA 误报** — 每次 QA 都会产生噪音
3. **#3 占位符扫描** — 每次都踩
4. **#4 route_matrix 类型校验** — 已两次踩坑
5. **#5-7** — 体验优化，非阻断
