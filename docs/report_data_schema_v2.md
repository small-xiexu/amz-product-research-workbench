# Report Data 数据结构扩展规范

**目的**: 支持产品图片和战场分级功能  
**影响文件**: `report_data.json`  
**版本**: v2.0 (2026-07-01)

---

## 📊 新增字段概览

### 1. 类目图片和分级

**位置**: `category_panorama.categories[]`

```json
{
  "category_panorama": {
    "categories": [
      {
        // 现有字段保持不变
        "category_name": "Pantry Storage Bins",
        "node_id": "3744021",
        "category_path": "Home & Kitchen > Kitchen & Dining > ...",
        "top100_monthly_sales": 500000,
        "top100_monthly_revenue": 8315000,
        "avg_price": 16.63,
        "brand_concentration": 0.302,
        
        // 新增字段
        "image_url": "https://m.media-amazon.com/images/I/71mMKhIfPKL._AC_SL1500_.jpg",
        "tier": "main"
      }
    ]
  }
}
```

---

### 2. 竞品图片

**位置**: `competitors[]`

```json
{
  "competitors": [
    {
      // 现有字段保持不变
      "asin": "B0DPSJP47V",
      "brand": "STWWO",
      "price_usd": 25.99,
      "monthly_units": 12000,
      "rating": 4.5,
      "review_count": 850,
      
      // 新增字段
      "image_url": "https://m.media-amazon.com/images/I/61qti20RbxL._AC_SL1500_.jpg"
    }
  ]
}
```

---

## 🔧 字段详细说明

### `image_url` (string, nullable)

**用途**: 存储Amazon产品主图URL

**来源**:
- 类目图片: Sorftime CategoryRequest API 返回的代表产品图片
- 竞品图片: 卖家精灵 ASIN详情API 返回的主图URL

**格式要求**:
- 必须是完整的URL，包含协议（https://）
- 推荐使用Amazon CDN: `https://m.media-amazon.com/images/I/{image_id}.jpg`
- 尺寸建议: 最小500px，推荐1000-1500px（CSS会自动缩放）

**默认值**:
- 可以为 `null` 或空字符串 `""`
- 当值为空时，报告生成器会显示占位符

**示例**:
```json
"image_url": "https://m.media-amazon.com/images/I/71mMKhIfPKL._AC_SL1500_.jpg"
```

---

### `tier` (string, nullable)

**用途**: 战场分级标识

**位置**: 仅用于 `category_panorama.categories[].tier`

**取值范围**:
- `"main"` - 主战场（核心必争）
- `"second"` - 次要战场（机会验证）
- `"edge"` - 边缘战场（观望待定）

**默认值**:
- 可以为 `null` 或空字符串 `""`
- 当值为空时，报告生成器按月销量排序后自动分级：
  - 前3个类目: `"main"`
  - 中间3个类目: `"second"`
  - 后3个类目: `"edge"`

**示例**:
```json
"tier": "main"
```

---

## 🎯 数据采集要求

### 阶段1: Sorftime API (类目图片)

**目标API**: `CategoryRequest` 或类似的类目详情API

**需要获取的字段**:
- `image_url` 或 `main_image` 或 `representative_image`
- 如果API不直接返回，可以从 `representative_asins` 中取第一个ASIN，然后查询其主图

**实现位置**:
- 数据采集脚本: `packages/sorftime_mcp/...` (具体文件待确认)
- 数据填充脚本: Stage 10 或 report_agent 的 seed 生成阶段

**伪代码**:
```python
def fetch_category_image(node_id: str) -> str | None:
    """获取类目代表产品图片"""
    response = sorftime_client.category_request(node_id=node_id)
    
    # 方案1: 直接返回
    if 'image_url' in response:
        return response['image_url']
    
    # 方案2: 从代表ASIN获取
    if 'representative_asins' in response and response['representative_asins']:
        first_asin = response['representative_asins'][0]
        asin_detail = get_asin_image(first_asin)
        return asin_detail.get('image_url')
    
    # 方案3: fallback
    return None
```

---

### 阶段2: 卖家精灵API (竞品图片)

**目标API**: ASIN详情查询API

**需要获取的字段**:
- `main_image_url` 或 `image` 或 `product_image`

**实现位置**:
- 数据采集脚本: `packages/sellersprite_mcp/...` (具体文件待确认)
- 数据填充脚本: Stage 10 竞品分析阶段

**伪代码**:
```python
def fetch_asin_image(asin: str) -> str | None:
    """获取ASIN主图"""
    response = sellersprite_client.get_asin_details(asin=asin)
    
    # 方案1: 直接返回
    if 'main_image_url' in response:
        return response['main_image_url']
    
    # 方案2: 备用字段
    if 'image' in response:
        return response['image']
    
    # 方案3: fallback
    return None
```

---

### 阶段3: 战场分级逻辑

**实现位置**: 
- Stage 10 Lead Operator Agent 的市场判断阶段
- 或 report_agent 的 seed 生成阶段

**分级标准**（建议）:
```python
def classify_category_tier(category: dict) -> str:
    """
    根据月销量和其他指标分级
    
    标准（可调整）:
    - 主战场: 月销量 > 300K 且差异化机会明确
    - 次要战场: 月销量 > 100K 或有明确验证路径
    - 边缘战场: 其他情况
    """
    monthly_sales = category.get('top100_monthly_sales', 0)
    
    # 简化规则: 按月销量分级
    if monthly_sales > 300000:
        return "main"
    elif monthly_sales > 100000:
        return "second"
    else:
        return "edge"
```

**注意**: 
- 这只是建议规则，实际分级应该由Lead Operator Agent基于综合判断
- 如果Lead Operator的判断中已包含分级，直接使用即可

---

## 🔄 向后兼容

### 现有报告不受影响

如果 `report_data.json` 中缺少新字段：
- `image_url` 缺失 → 显示占位符 📦
- `tier` 缺失 → 按月销量自动分级

### 渐进式增强

**第一步**: 仅CSS和设计规范（已完成）
- Report Generation Agent 可以使用新样式
- 即使没有图片数据，布局也正常

**第二步**: 数据采集增强（待实施）
- 修改数据采集脚本
- 填充 `image_url` 和 `tier` 字段

---

## 📝 示例：完整的类目数据

```json
{
  "category_name": "Pantry Storage Bins",
  "node_id": "3744021",
  "category_path": "Home & Kitchen > Kitchen & Dining > Kitchen Storage & Organization > Food Storage > Pantry Storage Bins",
  "top100_monthly_sales": 500000,
  "top100_monthly_revenue": 8315000,
  "product_count_in_category": 12500,
  "brand_concentration": 0.302,
  "representative_asins": ["B08X4YNVQR", "B09K7H2PQW"],
  "avg_price": 16.63,
  "category_role": "P1 · 主食品储藏箱",
  "reason": "核心路线，体量最大，差异化机会明确",
  "lineage": "主战场",
  "image_url": "https://m.media-amazon.com/images/I/71mMKhIfPKL._AC_SL1500_.jpg",
  "tier": "main"
}
```

---

## 📝 示例：完整的竞品数据

```json
{
  "asin": "B0DPSJP47V",
  "brand": "STWWO",
  "price_usd": 25.99,
  "monthly_units": 12000,
  "monthly_revenue": 311880,
  "rating": 4.5,
  "review_count": 850,
  "launch_date": "2024-01",
  "weakness": "评论提及配件易丢失",
  "image_url": "https://m.media-amazon.com/images/I/61qti20RbxL._AC_SL1500_.jpg"
}
```

---

## ✅ 验证清单

在数据采集脚本修改完成后，验证：

- [ ] `category_panorama.categories[].image_url` 字段存在且有效
- [ ] `category_panorama.categories[].tier` 字段存在且取值正确
- [ ] `competitors[].image_url` 字段存在且有效
- [ ] 图片URL可访问（HTTP 200）
- [ ] 图片URL格式正确（以 https:// 开头）
- [ ] 空值处理正常（不会导致报告生成失败）

---

**文档版本**: v2.0  
**创建日期**: 2026-07-01  
**状态**: 数据结构已定义，等待数据采集脚本实现
