# Seller Sprite Product Research

## 作用

这套 Skill 用来跑亚马逊选品初筛流程：

`输入品类 -> 拉卖家精灵 MCP 数据 -> 组织竞品池 -> 做利润/退货/知产/合规初筛 -> 生成报告三件套`

## 适用场景

- 新品类调研
- 竞品池初筛
- 利润参考测算
- 退货和风险初判
- 输出主报告、摘要和 HTML 看板

## 必填输入

- 站点
- 候选品类或关键词
- 产品形态
- 明确禁区

## 可选输入

- 产品属性勾选
- 目标售价区间
- 采购价
- 汇率
- FBA 费用
- 仓储费
- 入库配置费
- 退货率经验
- 广告费率经验
- 供应链备注

## 工作流程

1. 读取 V1 范围冻结和字段来源表。
2. 校验必填输入，不够就先追问。
3. 调用卖家精灵 MCP 拉取市场、关键词、Top100、竞品、趋势、商标等数据。
4. 生成竞品池：Top10 标杆组、近半年放量新品组、结构补充组。
5. 计算利润参考、头程、退货风险。
6. 做知产和合规初筛。
7. 组织成 `research_package`。
8. 渲染 `report.md`、`summary.md`、`dashboard.html`、`data.xlsx`。
9. 遇到高风险、低置信度、缺来源数据时，标记待复核，不硬猜。

## 硬规则

- Top100 不完整，不出正式结论。
- 没有来源和采集时间，不写强判断。
- 利润结果只写参考值。
- 仓储费早期按建议售价 3% 简化估算。
- FBA 费用、入库配置费、售价、采购价、退货率、广告费率由运营手填。
- 头程费用按计费重和渠道单价估算，计费重取体积重和实际重较大值。
- 评论插件不进 V1 初筛主流程。
- 知产、合规、最终状态保留人工复核。

## 输出

- `research_package.json`
- `data.xlsx`
- `report.md`
- `summary.md`
- `dashboard.html`

## 参考

- `README.md`
- `docs/V1范围冻结.md`
- `docs/字段来源表.md`
- `docs/静态报告Mock.md`
- `references/tool_mapping.md`
- `references/payload_schema.md`
- `references/decision_rules.md`
- `references/ip_compliance_links.md`
- `references/workspace_view_schema.md`
