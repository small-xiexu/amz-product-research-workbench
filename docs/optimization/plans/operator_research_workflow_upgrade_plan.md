# 运营式选品调研流程升级实施计划

更新日期：2026-06-19

这份文件是本次通用升级的进度台账。执行本计划时，以本文件为唯一进度记录；每完成一个可验收事项立即回写状态和验证结果。

## 当前状态

| 项 | 状态 |
|---|---|
| 阶段 | P0/P1/P2/P3/P4/P5 已完成 |
| 设计文档 | `docs/optimization/operator_research_workflow_upgrade.md` |
| 硬约束 | 通用化，不硬编码当前品类、ASIN、关键词、类目或供应商 |
| 采集口径 | Sorftime / 卖家精灵以判断质量优先，不以节省调用或导出为目标 |

## P0 必做

- [x] P0-1 更新主流程 Skill
  - 状态：已完成
  - 范围：`skills/amazon-product-research/SKILL.md`
  - 要求：流程改为“相似竞品 ASIN -> 大小类目 -> 反查关键词 -> 价格带/集中度/新品机会”
  - 验收：已更新主链路、Stage 1/2/4/5/7、硬规则和 DoD；硬编码扫描未发现当前案例词/ASIN/类目

- [x] P0-2 更新 Search Demand Agent
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/search-demand-agent.md`
  - 要求：输出运营式关键词池，包含词角色、来源、ASIN 覆盖、混池标签、推荐动作
  - 验收：已定义 `keyword_pool_by_role`、关键词对象字段、ASIN 覆盖、类目/关键词淡旺季分层和禁用规则；硬编码扫描未发现当前案例词/ASIN

- [x] P0-3 更新 Market Structure Agent
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/market-structure-agent.md`
  - 要求：输出参考 ASIN 池、候选类目池、小类目机会、价格带机会、新品机会
  - 验收：已定义 `reference_asin_pool`、`category_candidates`、`asin_category_mapping`、`price_band_opportunity`、`new_release_opportunity`；类目和价格带均要求标角色/证据；硬编码扫描未发现当前案例词/ASIN

- [x] P0-4 更新 Evidence Packet 契约
  - 状态：已完成
  - 范围：`skills/amazon-product-research/references/evidence_packet_contract.md`
  - 要求：新增 `reference_asin_pool`、`category_candidates`、`asin_category_mapping`、`keyword_pool_by_role`、`price_band_opportunity`、`new_release_opportunity`
  - 验收：已新增通用业务对象，并覆盖来源、角色、推荐用途、证据回表、data_gaps 和 Stage 7 必备结构；硬编码扫描未发现当前案例词/ASIN

- [x] P0-5 更新 Sorftime 调用策略
  - 状态：已完成
  - 范围：`docs/sorftime-mcp-工具调用策略.md`
  - 要求：取消省调用思路，按候选类目、参考 ASIN、词表分层完整采集
  - 验收：已重写为 Stage 1/Stage 7 通用调用策略，覆盖 ASIN 流量词、竞品关键词、类目报告、类目趋势、关键词扩展、关键词分层和 data_gaps；硬编码扫描未发现当前案例词/ASIN

- [x] P0-6 更新卖家精灵导出规范
  - 状态：已完成
  - 范围：`docs/卖家精灵导出指令完整性规范.md`
  - 要求：增加 `data_role`、候选小类、参考 ASIN、反查词、ABA、新品榜/榜单数据导出要求
  - 验收：已重写为通用导出清单，覆盖 `data_role`、大小类、参考 ASIN、反查、ABA、新品、混池对照、价格带字段和失败兜底；硬编码扫描未发现当前案例词/ASIN

- [x] P0-7 更新 Delivery QA Agent
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/delivery-qa-agent.md`
  - 要求：新增 ASIN 池、类目反推、关键词分层、价格带机会、淡旺季分层检查
  - 验收：已新增 `operator_workflow_issues`，覆盖“只用关键词定义市场”“类目未按 ASIN 反推”“关键词未分层”“只写均价”“用关键词旺季替代类目淡旺季”等检查；硬编码扫描未发现当前案例词/ASIN

## P1 报告与数据结构

- [x] P1-1 更新 Stage 7 报告模板
  - 状态：已完成
  - 范围：`scripts/build_stage7_analysis_report.py`
  - 要求：报告顺序改为参考 ASIN 池、大小类目、小类机会、价格带、词表、VOC、供应链
  - 验收：已新增参考 ASIN、类目机会、关键词池 HTML 章节和 `Reference ASINs`、`Category Candidates`、`Keyword Pool`、`Price Bands` Excel Sheet；脚本编译通过，硬编码扫描未发现当前案例词/ASIN

- [x] P1-2 更新 Lead Operator Agent
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/lead-operator-agent.md`
  - 要求：综合判断基于类目、ASIN、词表、价格带、VOC、供应链；不新增原始数字
  - 验收：已要求 memo 覆盖参考 ASIN、大小类目、小类机会、关键词池、价格带、VOC、供应链；利润/合规未回填前只允许继续看/谨慎继续/暂缓；硬编码扫描未发现当前案例词/ASIN

- [x] P1-3 更新 Report Writer
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/report-writer.md`
  - 要求：不把关键词表当市场结论；分开展示类目淡旺季和关键词热度月份
  - 验收：已更新 Stage 7 HTML/Excel 章节清单，要求展示参考 ASIN、类目候选、关键词池和价格带；明确禁止关键词表当市场结论、只写均价、关键词旺季替代类目淡旺季；硬编码扫描未发现当前案例词/ASIN

- [x] P1-4 更新相关 schema / 测试样例
  - 状态：已完成
  - 范围：`packages/research_core/schemas/`、`tests/`
  - 要求：结构化对象可被脚本和测试读取
  - 验收：已新增 `test_stage7_analysis_report_uses_operator_research_objects`，覆盖参考 ASIN、类目候选、关键词池、价格带、新品机会、HTML 章节和 Excel Sheet；新增单测通过，脚本和测试文件编译通过

## P2 增强

- [x] P2-1 新增关键词混池评分
  - 状态：已完成
  - 范围：`scripts/build_stage7_analysis_report.py`、`tests/test_regression.py`
  - 要求：按标题/类目/ASIN 命中识别 car、shower、liquid、cloth、screen、floor、brand 等混池标签
  - 验收：已新增通用 `mix_pool_score`、`mix_pool_risk_level`、推荐动作兜底和 HTML/Excel 展示；新增回归断言混池排除词高风险通过

- [x] P2-2 新增新品榜机会模块
  - 状态：已完成
  - 范围：`scripts/build_stage7_analysis_report.py`、`tests/test_regression.py`
  - 要求：按小类目判断新品数量、新品销量、低评论样本、榜单机会
  - 验收：已新增 `new_release_opportunity_score`、`new_release_opportunity_level`、评分原因和 HTML/Excel 展示；新增回归断言新品机会评分通过

- [x] P2-3 新增类目淡旺季模块
  - 状态：已完成
  - 范围：`scripts/build_stage7_analysis_report.py`、`tests/test_regression.py`
  - 要求：类目趋势独立于关键词趋势
  - 验收：已新增 `category_seasonality` 独立读取、HTML/Excel 展示和缺失 warning；新增回归断言类目淡旺季章节通过

## P3 手动采集指令补齐

- [x] P3-1 新增评论 VOC 导出指令完整性规范
  - 状态：已完成
  - 范围：`docs/评论VOC导出指令完整性规范.md`
  - 要求：评论/评价导出按插件实际操作收敛为 ASIN 清单，用户侧只需要粘贴 ASIN；ASIN 角色、路线和样本缺口由系统内部记录
  - 验收：已按 P4 修正为通用规范，覆盖可复制 ASIN 清单、建议站点、存放目录、导入命令和系统内部覆盖检查；未写入当前品类、ASIN、关键词或评论样本

- [x] P3-2 更新主流程和跑通手册
  - 状态：已完成
  - 范围：`skills/amazon-product-research/SKILL.md`、`skills/amazon-product-research/references/codex_runbook.md`
  - 要求：Stage 5/6 进入评论采集前必须输出评价 ASIN 清单，不能要求运营填写插件不需要的复杂条件
  - 验收：已在主 Skill 参考文档、运营采集指令、Stage 5 路线级小深挖、暂停点 5 和 Stage 6 中接入评价 ASIN 清单口径；跑通手册已要求输出可复制 ASIN 和 VOC 导入命令

- [x] P3-3 更新 VOC Evidence Agent
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/voc-evidence-agent.md`
  - 要求：VOC evidence 必须记录评论导出范围、ASIN 角色覆盖、路线覆盖和样本缺口
  - 验收：已按 P4 修正为评价 ASIN 清单输入、`review_export_scope`、`review_asin_plan`、`coverage_by_route`、`coverage_by_asin_role`、`review_quality_gaps`，并补充站点/地区、混池、HTML 边界和样本不足规则

- [x] P3-4 更新 Delivery QA
  - 状态：已完成
  - 范围：`skills/amazon-product-research/agents/delivery-qa-agent.md`
  - 要求：QA 能识别评价 ASIN 清单缺失、ASIN 角色缺失、低分评论不足、评论地区/站点不清、字段缺失未写缺口
  - 验收：已按 P4 修正为评价 ASIN 清单、ASIN 角色、路线覆盖、样本不足、地区口径、字段缺失和 HTML 摘要替代明细等 QA 问题；评价操作说明过度复杂会被标 warning

- [x] P3-5 同步单独评论 VOC Skill
  - 状态：已完成
  - 范围：`skills/review-voc-analysis/SKILL.md`
  - 要求：单独触发评论分析时，也必须先给运营评价 ASIN 清单，并使用正确 VOC 导入命令
  - 验收：已新增采集前置规则，要求按评论 VOC 导出规范输出 ASIN 清单；已修正 Excel/HTML 和 JSON 两种导入命令；覆盖范围核查已增加路线、价格带、ASIN 角色、站点和评论地区口径

## 通用验收清单

- [x] 未硬编码当前品类、ASIN、关键词、类目、供应商
- [x] 系统能自动生成运营式关键词池
- [x] 每条产品路线有参考 ASIN 池和选择理由
- [x] 类目由候选类目池 + ASIN 反推共同决定
- [x] 价格机会按价格段而不是均价表达
- [x] 品牌/商品集中度按小类目和价格段解释
- [x] 新品机会按小类目解释
- [x] 类目淡旺季和关键词热度分开展示
- [x] QA 能识别旧流程的关键误用
- [x] 用户手动导出/采集只分卖家精灵、评价、1688 三类；评价只给 ASIN 清单，卖家精灵和 1688 给详细条件

## P4 手动导出类型收敛

- [x] P4-1 收敛用户手动导出类型
  - 状态：已完成
  - 范围：`skills/amazon-product-research/SKILL.md`、`docs/评论VOC导出指令完整性规范.md`、`skills/amazon-product-research/references/codex_runbook.md`
  - 要求：项目只把用户手动导出分为卖家精灵、评价、1688 三类；评价只给 ASIN 清单，不要求运营填写评论范围、目标条数、字段等复杂条件
  - 验收：评价规范已改为只输出可复制 ASIN 清单、建议站点、存放目录和导入命令；主流程、跑通手册、VOC Evidence Agent、Delivery QA 和单独评论 Skill 已同步；卖家精灵和 1688 仍保留详细导出/采集条件

## P5 卖家精灵入口校准

- [x] P5-1 按真实菜单入口重写卖家精灵导出规范
  - 状态：已完成
  - 范围：`docs/卖家精灵导出指令完整性规范.md`、`skills/amazon-product-research/SKILL.md`、`skills/amazon-product-research/references/codex_runbook.md`
  - 要求：卖家精灵导出清单必须使用截图中的真实功能入口，不再写泛入口；区分大数据选品、运营推广、浏览器插件三组
  - 验收：已按截图菜单重写入口映射，覆盖大数据选品 / 查竞品、选产品、选市场、关键词选品、ABA数据选品、产品库，运营推广 / 查流量来源，浏览器插件 / 市场分析、关键词反查、评论下载；主流程 Stage 2、跑通手册和设计文档已同步；硬编码扫描未发现当前案例词/ASIN
