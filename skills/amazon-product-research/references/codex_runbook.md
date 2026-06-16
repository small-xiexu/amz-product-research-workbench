# Codex 跑通手册

当前目标：先跑通 Codex 版，不接 Web。

## 0. 初始对话

运营只需要说自然语言意图，例如：

```text
我想看美国站宠物牵引绳方向。
```

Codex 需要先判断路径：

- 模糊大类：无方向探索
- 明确品类：指定方向深挖

默认站点为 `US`。

## 1. 建立 run 目录

```text
runs/<yyyymmdd>_<direction>/
├── inputs/seller_sprite/
├── inputs/reviews/
└── mcp/
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
4. `ali1688_similar_product`（必须用中文品类词，返回 1688 中国站人民币采购价；优先看一件代发/现货信号）

1688 口径：

- 当前访问链路是 Sorftime MCP 代理，不是项目直接打开 `https://www.1688.com/` 抓网页。
- 原始来源必须是 1688 中国站，入口口径 `https://www.1688.com/`，详情页接受 `https://detail.1688.com/offer/...` 等 `*.1688.com`。
- 原始价格字段按 RMB/CNY 记录；折 USD 只能作为报告展示。
- Alibaba 国际站 USD 报价、非 1688 域名或币种不明样本，不进入采购价区间。

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

- 搜索结果
- 市场分析 Top100 完整版
- 关键词反查
- ABA 关键词整理

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

## 7. 规划评论 ASIN

候选池确认后，Codex 输出评论抓取 ASIN 批次：

- 量级标杆
- 近期新品
- 差评高发
- 功能差异
- 价格带代表

运营用自有评论插件导出到：

```text
runs/<run_id>/inputs/reviews/
```

## 8. 重跑正式报告

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

## 9. 校验

```bash
python3 scripts/validate_research_outputs.py runs/<run_id>
```

只有校验通过，才算 Codex 版本轮跑通。
