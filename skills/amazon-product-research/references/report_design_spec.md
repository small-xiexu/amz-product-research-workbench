# Stage 12 报告视觉设计规范

本文件规定 `<中文品名>_分析报告.html` 的视觉标准。**CSS 源码唯一事实源：`references/report_template.css`。** AI 手写 HTML 时必须把该文件全部内容复制到 `<style>` 块中，生成自包含的单文件，运营收到后直接双击打开即可看到完整样式。

**最新更新**：2026-07-01 增加看板式导航模式，提供更好的用户体验。

---

## 0. 看板式导航结构（必须使用）

报告必须使用看板式导航，结构如下：

```html
<div class="page">
  <!-- Hero：始终可见 -->
  <section class="hero">...</section>

  <!-- 看板导航：6个标签页 -->
  <nav class="dash-nav" role="tablist" aria-label="看板导航">
    <button class="dash-tab active" role="tab" data-target="pg-overview" aria-selected="true">
      <span class="tab-ico">①</span><span class="tab-label">总览研判</span>
    </button>
    <button class="dash-tab" role="tab" data-target="pg-category" aria-selected="false">
      <span class="tab-ico">②</span><span class="tab-label">候选类目</span>
    </button>
    <button class="dash-tab" role="tab" data-target="pg-rival" aria-selected="false">
      <span class="tab-ico">③</span><span class="tab-label">核心竞品</span>
    </button>
    <button class="dash-tab" role="tab" data-target="pg-route" aria-selected="false">
      <span class="tab-ico">④</span><span class="tab-label">路线定价</span>
    </button>
    <button class="dash-tab" role="tab" data-target="pg-traffic" aria-selected="false">
      <span class="tab-ico">⑤</span><span class="tab-label">关键词流量</span>
    </button>
    <button class="dash-tab" role="tab" data-target="pg-execute" aria-selected="false">
      <span class="tab-ico">⑥</span><span class="tab-label">落地风险</span>
    </button>
  </nav>

  <!-- 分页内容 -->
  <main class="dash-main">
    <div class="dash-page active" id="pg-overview" role="tabpanel" aria-label="总览研判">
      <!-- 资深运营评估 + 产品路线对比 -->
    </div>
    <div class="dash-page" id="pg-category" role="tabpanel" aria-label="候选类目">
      <!-- 类目全景 -->
    </div>
    <div class="dash-page" id="pg-rival" role="tabpanel" aria-label="核心竞品">
      <!-- 核心竞品 -->
    </div>
    <div class="dash-page" id="pg-route" role="tabpanel" aria-label="路线定价">
      <!-- 用户痛点 → 产品规格 + 价格带分布 -->
    </div>
    <div class="dash-page" id="pg-traffic" role="tabpanel" aria-label="关键词流量">
      <!-- 关键词与流量策略 -->
    </div>
    <div class="dash-page" id="pg-execute" role="tabpanel" aria-label="落地风险">
      <!-- 当前市场判断结论 + 进入落地阶段后的验证路线图 + 风险与下一步 -->
    </div>
  </main>

  <!-- JavaScript 交互逻辑 -->
  <script>...</script>
</div>
```

### 标签页内容分组

| 标签页 | 包含的 section | 说明 |
|---|---|---|
| ①总览研判 | 资深运营评估、产品路线对比 | 首页，市场机会判断 |
| ②候选类目 | 类目全景 | 9个候选类目分级展示 |
| ③核心竞品 | 核心竞品 | 竞品分析表格 |
| ④路线定价 | 用户痛点→产品规格、价格带分布 | 痛点+定价策略 |
| ⑤关键词流量 | 关键词与流量策略 | 关键词分析 |
| ⑥落地风险 | 当前市场判断结论、进入落地阶段后的验证路线图、风险与下一步 | 决策支持 |

### JavaScript 交互逻辑（必须添加）

在 `</body>` 前必须添加以下 JavaScript：

```javascript
<script>
(function(){
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.dash-tab'));
  var pages = Array.prototype.slice.call(document.querySelectorAll('.dash-page'));

  function activate(id, push){
    var found = false;
    pages.forEach(function(p){
      var on = p.id === id;
      p.classList.toggle('active', on);
      if(on) found = true;
    });
    tabs.forEach(function(t){
      var on = t.getAttribute('data-target') === id;
      t.classList.toggle('active', on);
      t.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    if(found){
      if(push && history.replaceState){
        history.replaceState(null, '', '#' + id);
      }
      var nav = document.querySelector('.dash-nav');
      if(nav){
        var y = nav.getBoundingClientRect().top + window.pageYOffset - 8;
        window.scrollTo({top: y < 0 ? 0 : y, behavior: 'smooth'});
      }
    }
  }

  tabs.forEach(function(t){
    t.addEventListener('click', function(){
      activate(t.getAttribute('data-target'), true);
    });
    t.addEventListener('keydown', function(e){
      var idx = tabs.indexOf(t);
      if(e.key === 'ArrowLeft' && idx > 0){ tabs[idx - 1].click(); e.preventDefault(); }
      if(e.key === 'ArrowRight' && idx < tabs.length - 1){ tabs[idx + 1].click(); e.preventDefault(); }
    });
  });

  // 从URL恢复状态
  if(window.location.hash){
    var target = window.location.hash.substring(1);
    if(document.getElementById(target)){
      activate(target, false);
    }
  }
})();
</script>
```

---

## 1. 战场分级与类目卡片（候选类目展示）

### 1.1 战场分级结构

候选类目按战场层级分类展示，使用三级分级：

**HTML结构**:
```html
<!-- 主战场 -->
<div class="tier-block tier-main">
  <div class="tier-head">
    <span class="tier-badge">主战场</span>
    <span class="tier-note">核心必争 · 体量最大 / 差异化最强，优先落地</span>
  </div>
  <div class="cat-nav">
    <!-- 类目卡片列表 -->
  </div>
</div>

<!-- 次要战场 -->
<div class="tier-block tier-second">
  <div class="tier-head">
    <span class="tier-badge">次要战场</span>
    <span class="tier-note">机会验证 · 差异化可攻但需交叉验证</span>
  </div>
  <div class="cat-nav">
    <!-- 类目卡片列表 -->
  </div>
</div>

<!-- 边缘战场 -->
<div class="tier-block tier-edge">
  <div class="tier-head">
    <span class="tier-badge">边缘战场</span>
    <span class="tier-note">观望待定 · 风险较高或数据不足</span>
  </div>
  <div class="cat-nav">
    <!-- 类目卡片列表 -->
  </div>
</div>
```

**战场分级标准**:
- **主战场（tier-main）**: 绿色徽章，月销量高 + 差异化强 + 竞争格局好
- **次要战场（tier-second）**: 黄色徽章，有机会但需要进一步验证
- **边缘战场（tier-edge）**: 灰色徽章，月销量低或竞争过于激烈

**数据字段要求**:
- `report_data.json` 中的 `category_panorama.categories[].tier` 字段
- 取值：`"main"` | `"second"` | `"edge"`
- 如果字段缺失，默认按月销量排序，前3个为主战场，中间3个为次要，后3个为边缘

---

### 1.2 类目卡片样式

每个候选类目使用卡片展示，包含产品图片、类目信息、关键指标。

**HTML结构**:
```html
<a class="cat-card" href="https://www.amazon.com/b?node={node_id}" target="_blank" rel="noopener">
  <div class="cc-top">
    <img src="{image_url}" alt="{category_name}" loading="lazy">
    <div>
      <div class="cc-name">{category_name} <span class="ext-ico">↗</span></div>
      <div class="cc-cn">{chinese_name} · Node {node_id}</div>
    </div>
  </div>
  <div class="cc-route">
    <span class="pill">{route_name}</span>
  </div>
  <div class="cc-meta">
    <span>Top100月销 <b>{monthly_sales}</b></span>
    <span>均价 <b>${avg_price}</b></span>
  </div>
  <div class="cc-meta">
    <span>头部品牌 {top_brand} {concentration}%</span>
  </div>
  <div class="cc-cta">点击卡片 → 跳转 Amazon 类目前台</div>
</a>
```

**数据字段映射**:
- `{image_url}`: `category.image_url` - 类目代表产品图片URL
- `{category_name}`: `category.category_name` - 类目英文名
- `{chinese_name}`: 从 `category.category_path` 或 `category_role` 提取中文名
- `{node_id}`: `category.node_id` - Amazon类目节点ID
- `{route_name}`: 从 `category.category_role` 或路线映射表获取
- `{monthly_sales}`: `category.top100_monthly_sales` - 格式化显示（如 219,100）
- `{avg_price}`: `category.avg_price` - 格式化显示（如 $23.83）
- `{top_brand}`: 从 `category.representative_asins` 或品牌数据提取
- `{concentration}`: `category.brand_concentration` - 头部品牌集中度

**图片缺失处理**:
```html
<!-- 如果 image_url 为空或未定义 -->
<img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='62' height='62'%3E%3Crect fill='%23f5f0eb' width='62' height='62'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-size='24'%3E📦%3C/text%3E%3C/svg%3E" 
     alt="占位符" 
     loading="lazy">
```
或者使用CSS伪元素显示占位符（已在CSS中定义）。

---

### 1.3 产品缩略图（竞品表格）

在核心竞品表格的ASIN列显示产品缩略图。

**HTML结构**:
```html
<td class="asin-cell">
  <a href="https://www.amazon.com/dp/{asin}" target="_blank" rel="noopener">
    <img class="prod-thumb" src="{image_url}" alt="{brand} {asin}" loading="lazy">
    <span class="asin-link">{asin} <span class="ext-ico">↗</span></span>
  </a>
</td>
```

**数据字段映射**:
- `{asin}`: `competitor.asin`
- `{image_url}`: `competitor.image_url` - 竞品ASIN主图URL
- `{brand}`: `competitor.brand`

**图片缺失处理**:
```html
<!-- 如果 image_url 为空，显示纯文本 -->
<td class="asin-cell">
  <a href="https://www.amazon.com/dp/{asin}" target="_blank" rel="noopener">
    <span class="asin-link">{asin} <span class="ext-ico">↗</span></span>
  </a>
</td>
```

---

### 1.4 路线对比表中的缩略图

在"产品路线对比"表格中，路线列可以显示代表产品的缩略图。

**HTML结构**:
```html
<td>
  <a class="cat-inline" href="https://www.amazon.com/b?node={node_id}" target="_blank" rel="noopener">
    <img class="cat-thumb" src="{image_url}" alt="{route_name}" loading="lazy">
    <span class="route-name">{route_name}（{chinese_name}）<span class="ext-ico">↗</span></span>
  </a>
</td>
```

**数据字段映射**:
- `{route_name}`: 路线英文名
- `{chinese_name}`: 路线中文名
- `{node_id}`: 类目节点ID
- `{image_url}`: 路线代表产品图片URL

---

## 2. 引用方式（强制）

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
| 价格柱状图 | `.price-band > .price-bar > .bar + .label` | 价格带板块；柱体底部必须共享同一基线，说明文字放在 `.label` |
| 下一步卡片 | `.next-steps > .next-step > .num + h4 + p` | 风险和下一步板块末尾 |
| 验证路线图 | `.validation-roadmap > .roadmap-phase > .phase-header + .phase-actions + .phase-exit + .phase-fail` | 验证路线图板块，按时间线组织的验证计划 |
| 风险列表 | `ul.risk-list > li > .severity + 内容` | 风险/优势双栏内部 |
| 放行条件表 | `table.go-nogo > thead > tr > th*4` + `tbody` | 风险和下一步板块中段 |
| 宽表滚动容器 | `.table-scroll > table` | 所有表格统一包裹；短表至少铺满容器，长表横向滚动 |

## 3. 标签仅 5 种

| 标签 | 用途 |
|---|---|
| `tag-green` | 正面：主战场、低门槛、有机会、已验证 |
| `tag-amber` | 需注意：次要战场、中等风险、需验证 |
| `tag-red` | 风险/否定：高壁垒、错误挂载、排除 |
| `tag-blue` | 数据标注：信息性、指标、类别（中性） |
| `tag-gray` | 中性标注：待确认、信息不足 |

**禁止**新增 tag-purple 等额外颜色。

## 4. 报告结构

报告不固定要求“数据来源与口径”独立板块。可在业务板块中自然表达“样本边界 / 判断口径”，但不能暴露 MCP、Agent、tool、packet、source_path、冲突复核过程或内部数据来源分歧。

推荐顺序：

1. **Hero** -- 一句话结论 + 关键 KPI。lead 保持 1-2 句精简。
2. **资深运营评估** -- 市场判断 / 机会判断 / 瓶颈与建议，三小节叙事。
3. **产品路线对比** — 路线表格（含 tradeoff 列"选了它你就放弃了什么"）+ 推荐策略/搁置双卡片
4. **类目全景** — 表格 + 2 列洞察卡片
5. **核心竞品** — 竞品弱点地图（含"主要差评点"+"我的反击"列），每条路线 ≥2 个 ASIN
6. **用户痛点 → 产品规格** — 必须验证 / 重点优化 / 建议优化 + 规格建议
7. **价格带分布** — flex 柱状图 + 表格
8. **关键词与流量策略** — 按意图三分：主攻/可测/否定
9. **验证路线图** — 按时间线组织的验证计划（每周动作 + 通过标准 + 失败分支），不是平铺的下一步
10. **风险与放行条件** — 风险/优势双栏 + 放行条件表

## 5. 禁止事项

| 禁止 | 正确做法 |
|---|---|
| `<link>` 引用外部 CSS | 把 `report_template.css` 全部内容内嵌到 `<style>` 块 |
| 深灰/黑色 Hero | 蓝色渐变（CSS 已定义） |
| 裸内容无 `.section` 包裹 | 每个板块进 `.section` 卡片 |
| 超过 5 种 tag 颜色 | 只用 green/amber/red/blue/gray |
| 价格带只用表格 | flex 柱状图 + 表格配合 |
| max-width 不是 1100px | CSS 已设置 1100px |
| 下一步用普通列表 | 验证路线图（`.next-step` 编号卡片，含时间/动作/标准/失败分支） |
| 表格缩成半截或不居中 | 所有表格包裹 `.table-scroll`，table 至少 `min-width:100%` 且居中 |
| 类目全景只列一个类目 | 列出所有相关类目 |
| HTML 中出现 Agent/MCP/tool/spawn/packet/source_path/冲突复核过程 | 改成运营可读的样本边界、判断口径或验证动作 |

## 6. Excel 决策工具包规格

XLSX 不是数据回表，是运营可以直接用的决策工具包。与 HTML 报告互补——HTML 讲判断逻辑，Excel 给操作数据。

| Sheet | 用途 | 核心列 |
|---|---|---|
| 路线计分卡 | 每条路线 × 6 维度评分 + 一句话判断。运营可改权重重新排序 | 路线名、市场需求、竞争结构、价格带机会、VOC机会、风险、数据质量、综合、一句话判断 |
| 竞品拆解 | 每个核心竞品的完整画像 | ASIN、品牌、月销、价格、评分、评论数、路线、主要差评点（VOC原文引用）、可抄的优点、我的反击方案 |
| 关键词矩阵 | 运营可以直接拿去建广告组 | 关键词、意图分类（主攻/可测/否定）、月搜量、CPC、竞品数、策略说明 |
| 样品检查表 | VOC 痛点 → 测试项 → 通过标准，运营填实际结果 | 痛点维度、优先级、竞品问题描述、测试项、通过标准、实际结果（运营填）、是否通过（运营填） |

**硬规则**：
- Excel 中所有预估数字必须标注"数量级估算，实际取决于XXX"
- 运营填写列必须留空，不填默认值
- 禁止在 Excel 中出现 Agent/MCP/tool/source_path 等内部术语

## 7. 写前检查

- [ ] HTML 内嵌 `<style>` 块（内容来自 `report_template.css`），不使用 `<link>`
- [ ] Hero 存在且有 `.verdict` 结论标签
- [ ] 所有板块用 `.section` 包裹
- [ ] 标签仅 green/amber/red/gray
- [ ] 价格带有 `.price-band` 柱状图
- [ ] 类目全景列出所有相关类目
- [ ] 洞察卡片有 `.good` / `.warn` 左边框
- [ ] 验证路线图按时序组织（非平铺待办），每步含通过标准+失败分支
- [ ] 竞品弱点有差评原文引用，反击方案具体到可写进Listing
- [ ] 全文无内部术语
- [ ] 用词克制，事实和推断分开
