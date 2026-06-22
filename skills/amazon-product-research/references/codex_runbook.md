# Codex 跑通手册

> **LEGACY** — 本文档描述的是旧脚本驱动工作流（依赖 `workflow_state.json`、`import_manifest.json` 等旧产物）。当前主链路已切换为 AI 交互推进模式，产物契约以 `artifact_contract.md` 为准。本文档仅供历史参考。

当前目标：先跑通 Codex 版，不接 Web。

## 0. 初始对话

运营只需要说自然语言意图，例如：

```text
我想看美国站某个具体方向。
```

Codex 需要先判断路径：

- 模糊大类：无方向探索
- 明确品类：指定方向深挖

默认站点为 `US`。

## 1. 建立 run 目录

```text
runs/<yyyymmdd>_<中文品类方向>/
├── progress.json            # 断点恢复，AI 在关键节点自动写入
├── inputs/
│   ├── seller_sprite/       # 运营导出卖家精灵原始文件
│   └── reviews/             # 运营导出评论原始文件
├── mcp/                     # Sorftime MCP 快照
├── candidate_pool.json
├── route_matrix_confirm.json
├── market_structure/
│   └── market_structure_evidence_packet.json
├── search_demand/
│   └── search_demand_evidence_packet.json
├── review_voc/
│   ├── review_voc_package.json
│   ├── voc_evidence_packet.json
│   └── voc_evidence.xlsx
└── analysis/                # Stage 7 最终交付
    ├── <中文品名>_分析报告.html
    ├── <中文品名>_数据回表.xlsx
    ├── report_data.json
    └── delivery_qa_result.json
```

## 2. 生成 workflow_state

```bash
python3 scripts/plan_interactive_workflow.py \
  runs/<run_id>/workflow_state.json \
  --mode targeted_deep_dive \
  --intent "<运营意图>" \
  --site US \
  --workflow-id <run_id>
```

输出后先看是否 `Decision required: True`。如果需要运营确认，不继续跑后续脚本。

## 3. Sorftime MCP 快验

指定方向深挖优先做快验：

1. `category_search_from_product_name`
2. `category_report`
3. `keyword_detail`
4. `keyword_search_results`
5. 必要时补 `potential_product` 或 `similar_product_feature`

把结果保存到：

```text
runs/<run_id>/mcp/
```

并整理成：

```text
runs/<run_id>/mcp/sorftime_verification.json
```

## 4. 引导卖家精灵导出

Codex 给运营导出清单：

- 大数据选品 / 选市场：候选大类、候选小类、ASIN 反推小类，用于市场容量、价格带、集中度、新品机会和类目淡旺季。
- 大数据选品 / 查竞品：相似卖点关键词、候选小类、对照词，用于建立参考 ASIN 池和混池边界。
- 大数据选品 / 选产品：产品形态词、路线词、候选小类，用于补充候选商品、新品和低评论样本。
- 浏览器插件 / 关键词反查：参考 ASIN Top5/Top10，用于整理运营式关键词池。
- 大数据选品 / ABA数据选品：主查词、补查词、路线词，用于搜索、点击和转化集中度。

卖家精灵输入口径：

- 路线名可以用中文写给运营看，但实际复制到卖家精灵的输入对象必须使用目标站点语言；美国站、加拿大站和英国站默认使用英文关键词或英文类目名。
- 中文内部路线名只作为说明，不要混进卖家精灵的 `查竞品`、`选产品`、`选市场`、`关键词选品` 或 `ABA数据选品`。
- 排除关键词也按站点语言填写；美国站用 `electric, vacuum, spray, liquid, floor, car detailing, window film` 这类英文词。

运营把文件放到：

```text
runs/<run_id>/inputs/seller_sprite/
```

## 5. 盘点导出文件

```bash
python3 scripts/inspect_manual_exports.py \
  runs/<run_id>/inputs/seller_sprite \
  runs/<run_id>/import_manifest.json \
  --site US \
  --task-name "<本轮方向>"
```

如果缺 Top100、ABA 或关键词反查，先让运营补导，不进入正式深挖。

## 6. 构建候选池

```bash
python3 scripts/build_candidate_pool_from_import_manifest.py \
  runs/<run_id>/import_manifest.json \
  runs/<run_id>/candidate_pool.json \
  --sorftime-verification runs/<run_id>/mcp/sorftime_verification.json
```

如果当前 CLI 参数和脚本不一致，优先用 `scripts/run_research_workflow.py` 的 `--sorftime-verification` 路径完成合并。

## 7. 评论前轻量 Sorftime 路线校准

候选池确认后、规划评价 ASIN 清单前，先按 Search Demand Agent 口径做轻量路线校准。默认写入：

```text
runs/<run_id>/mcp/route_sorftime_calibration.json
```

最低覆盖：

- 候选小类或混池高风险类目的 `category_report`、`category_trend` 或历史报告复用。
- 2-3 个代表 ASIN 的 `product_traffic_terms`，覆盖主线标杆、高客单/升级、新品或低评有量样本。
- 1-2 个核心词的 `keyword_extends`，以及主线词、场景词或精准长尾词的 `keyword_detail`。
- 混池风险高时补 `keyword_search_results` 或 `competitor_product_keywords`。
- 必要时补 `similar_product_feature`，用于提炼热销共同特征和规格验证项。

校准结论只用于调整路线边界和评价 ASIN 批次：保留、观察、合并、排除、补抓、替换或标记对照。无法调用或数据不足时，必须在 `data_gaps` 写清，再决定是否继续评论采集。

## 8. 规划评价 ASIN 清单

候选池确认后，Codex 必须按 `docs/评论VOC导出指令完整性规范.md` 输出评价 ASIN 清单。评价插件侧只需要 ASIN，不要求运营填写评论范围、目标条数、字段筛选或低星筛选。

- 本轮评论数据放置目录
- 评论慢速采集助手入口
- 建议站点
- 可复制 ASIN 清单，一行一个
- 文件命名、存放目录和导入命令

系统内部记录 ASIN 角色和选择理由，至少覆盖：

- 主推代表
- 量级标杆
- 近期新品
- 差评高发或痛点参考
- 高客单或价格带代表
- 混池/旁支对照，如有必要

运营用自有评论插件导出到：

```text
runs/<run_id>/inputs/reviews/
```

评论导出完成后，先生成 VOC 数据包：

```bash
python3 scripts/build_review_voc_from_plugin_export.py \
  runs/<run_id>/review_voc \
  runs/<run_id>/inputs/reviews/<review.xlsx> \
  runs/<run_id>/inputs/reviews/<review-report.html> \
  --candidate-id <candidate_id> \
  --candidate-name "<候选名称>"
```

## 9. 重跑正式报告

```bash
python3 scripts/run_research_workflow.py \
  runs/<run_id>/inputs/seller_sprite \
  runs/<run_id> \
  --site US \
  --task-name "<本轮方向>" \
  --workflow-state runs/<run_id>/workflow_state.json \
  --sorftime-verification runs/<run_id>/mcp/sorftime_verification.json \
  --review-input runs/<run_id>/inputs/reviews/<review.xlsx> \
  --review-input runs/<run_id>/inputs/reviews/<review-report.html>
```

## 10. 校验

```bash
python3 scripts/validate_research_outputs.py runs/<run_id>
```

只有校验通过，才算 Codex 版本轮跑通。
