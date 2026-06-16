# Codex 选品链路

当前阶段先跑通 Codex 版：`skills + MCP + 本地脚本 + 报告`。Web 先不管，等底层链路稳定后再接。

## 定位

Codex 是运营的选品协作助手，不是一次性报告机器。

它要做三件事：

1. 判断当前处于哪一步。
2. 决定下一步是调 MCP、让运营导出、让运营抓评论，还是暂停让运营决策。
3. 把过程沉淀到最终报告和 Excel 证据链。

## 主流程

```text
意图输入
-> AI 判断模式
-> Sorftime MCP 快验
-> 卖家精灵导出清单
-> 导出文件盘点
-> 候选池生成
-> 主线/边界确认
-> 评论 ASIN 批次
-> 评论 VOC 导入
-> 利润/合规模板
-> 最终报告
-> 交付校验
```

## 两种内部模式

| 模式 | 触发 | 第一动作 |
|---|---|---|
| 无方向探索 | 只有模糊大类或偏好 | 拆 2-4 个候选方向，先轻量 MCP/导出宽扫 |
| 指定方向深挖 | 已有明确产品方向 | 先 Sorftime 快验，值得继续再让运营导出 |

运营不需要手动选择模式，Codex 根据自然语言判断。

## 关键暂停点

| 节点 | 为什么暂停 |
|---|---|
| 方向确认 | 防止 AI 误解运营目标 |
| 导出清单确认 | 防止导错关键词和报表 |
| 数据盘点后 | Top100/ABA/关键词反查缺失会影响结论 |
| 候选池后 | 需要运营选主线 |
| 边界确认 | 防止混池产品进入深挖 |
| 评论 ASIN 前 | 抓评论有成本，要确认批次 |
| 利润/合规前 | 这些必须人工复核 |
| 最终决策 | Go/Wait/No-Go 要由运营承接行动 |

## 数据源职责

| 数据源 | 用途 |
|---|---|
| Sorftime MCP | 类目节点、Top100、关键词、竞品、1688 中国站人民币采购价粗估 |
| 卖家精灵导出 | 搜索结果、市场分析、ABA、关键词反查 |
| 自有评论插件 | 差评痛点、好评卖点、VOC 证据 |
| 人工模板 | 利润、知产、合规最终补充 |

## 1688 采购价口径

- 当前不直接抓 `https://www.1688.com/` 页面，而是通过 Sorftime MCP `ali1688_similar_product` 间接查询。
- 原始来源必须是 1688 中国站：入口口径 `https://www.1688.com/`，商品详情页接受 `https://detail.1688.com/offer/...` 等 `*.1688.com`。
- 原始价格必须按 RMB/CNY 处理；报告中的 USD 只能是汇率折算展示。
- Alibaba 国际站 USD 报价、非 `1688.com` 链接、币种不明样本，不进入采购价区间，只能作为待复核记录。

## 脚本职责

| 脚本 | 职责 |
|---|---|
| `plan_interactive_workflow.py` | 生成/推进流程状态 |
| `inspect_manual_exports.py` | 盘点卖家精灵导出 |
| `build_candidate_pool_from_import_manifest.py` | 生成候选池 |
| `apply_sorftime_verification.py` | 合并 Sorftime 验证快照 |
| `build_review_voc_from_plugin_export.py` | 导入评论插件数据 |
| `run_research_workflow.py` | 数据齐全后重跑正式报告 |
| `validate_research_outputs.py` | 校验交付完整性 |

## 完成标准

一轮 Codex 版跑通必须满足：

- 有独立 `runs/<run_id>/` 目录。
- 有 `workflow_state.json`。
- 有 MCP 快验记录，或明确说明为什么暂不调用。
- 有卖家精灵导出盘点，或明确停在等待导出。
- 有候选池和边界确认。
- 有评论 VOC，或明确待抓 ASIN。
- 有最终报告五件套。
- `validate_research_outputs.py` 通过。

没有通过校验，不算完成。
