# Stage 7 报告视觉设计规范

本文件规定 `<中文品名>_分析报告.html` 的视觉标准。**CSS 源码唯一事实源：`references/report_template.css`。** AI 手写 HTML 时必须把该文件全部内容复制到 `<style>` 块中，生成自包含的单文件，运营收到后直接双击打开即可看到完整样式。

---

## 1. 引用方式（强制）

HTML 放在 `runs/<run_id>/analysis/` 下。**必须内嵌 CSS，禁止使用外部 `<link>` 引用。** 运营拿到的是单个 HTML 文件，不能依赖项目目录里的 CSS 文件。

AI 写报告时：先 Read `references/report_template.css`，把全部内容原样写入 HTML 的 `<style>` 块中。不要自己手写 CSS，不要修改 CSS 变量和选择器。

HTML 中只写内容结构（`.page > .hero + .section`），所有样式由内嵌 CSS 提供。禁止额外写第二个 `<style>` 块覆盖样式。

---

## 2. 组件使用规则

| 组件 | HTML 模式 | 何时用 |
|---|---|---|
| Hero | `.hero > .eyebrow + h1 + .verdict + .lead + .hero-grid` | 报告首屏，必须第一个 |
| Section 卡片 | `.section > h2 + .subtitle + 内容` | 每个板块必须包裹 |
| 洞察卡片 | `.insight-row > .insight-card.good\|.warn` | 类目全景展开、风险/优势双栏 |
| 标签 | `.tag.tag-green\|tag-amber\|tag-red\|tag-gray` | 表格判断列、状态标注 |
| 价格柱状图 | `.price-band > .price-bar > .bar + .label` | 价格带板块，必须配合表格 |
| 下一步卡片 | `.next-steps > .next-step > .num + h4 + p` | 风险和下一步板块末尾 |
| 风险列表 | `ul.risk-list > li > .severity + 内容` | 风险/优势双栏内部 |
| Go/No-Go 表 | `table.go-nogo > thead > tr > th*4` + `tbody` | 风险和下一步板块中段 |

## 3. 标签仅 4 种

| 标签 | 用途 |
|---|---|
| `tag-green` | 正面：主战场、低门槛、有机会、已验证 |
| `tag-amber` | 需注意：次要战场、中等风险、需验证 |
| `tag-red` | 风险/否定：高壁垒、错误挂载、排除 |
| `tag-gray` | 中性标注：待确认、信息不足 |

**禁止**新增 tag-blue、tag-purple 等额外颜色。

## 4. 报告结构

报告不固定要求“数据来源与口径”独立板块。可在业务板块中自然表达“样本边界 / 判断口径”，但不能暴露 MCP、Agent、tool、packet、source_path、冲突复核过程或内部数据来源分歧。

推荐顺序：

1. **Hero** — 绿色渐变，一句话结论 + 关键 KPI
2. **类目全景** — 表格 + 2 列洞察卡片
3. **核心竞品** — 竞品对比表，每条路线 ≥2 个 ASIN
4. **用户痛点 → 产品规格** — P0/P1/P2 + 规格建议
5. **价格带分布** — flex 柱状图 + 表格
6. **关键词与流量策略** — 按意图三分：主攻/可测/否定
7. **风险与下一步** — 风险/优势双栏 + Go/No-Go 表 + 3 张下一步卡片

## 5. 禁止事项

| 禁止 | 正确做法 |
|---|---|
| `<link>` 引用外部 CSS | 把 `report_template.css` 全部内容内嵌到 `<style>` 块 |
| 深灰/黑色 Hero | 绿色渐变（CSS 已定义） |
| 裸内容无 `.section` 包裹 | 每个板块进 `.section` 卡片 |
| 超过 4 种 tag 颜色 | 只用 green/amber/red/gray |
| 价格带只用表格 | flex 柱状图 + 表格配合 |
| max-width 不是 1100px | CSS 已设置 1100px |
| 下一步用普通列表 | 3 列 `.next-step` 编号卡片 |
| 类目全景只列一个类目 | 列出所有相关类目 |
| HTML 中出现 Agent/MCP/tool/spawn/packet/source_path/冲突复核过程 | 改成运营可读的样本边界、判断口径或验证动作 |

## 6. 写前检查

- [ ] HTML 内嵌 `<style>` 块（内容来自 `report_template.css`），不使用 `<link>`
- [ ] Hero 存在且有 `.verdict` 结论标签
- [ ] 所有板块用 `.section` 包裹
- [ ] 标签仅 green/amber/red/gray
- [ ] 价格带有 `.price-band` 柱状图
- [ ] 类目全景列出所有相关类目
- [ ] 洞察卡片有 `.good` / `.warn` 左边框
- [ ] 下一步是 3 张 `.next-step` 编号卡片
- [ ] 全文无内部术语
- [ ] 用词克制，事实和推断分开
