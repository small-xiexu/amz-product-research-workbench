# Stage 12 Contract — report_data.json

**产出方**: Report Generation Agent
**消费方**: `validate_report_data_completeness.py`, `build_report_xlsx.py`, Stage 13 QA
**输出路径**: `analysis/report_data.json`

## 必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"p8-report-data-v1"` |
| `packet_id` | string | `"report_data"` |
| `run_id` | string | run 目录名 |
| `competitors` | list[dict] | 竞品列表，≥ 1 |
| `keywords` | list[dict] | 关键词列表，≥ 1 |
| `product_routes` | list[dict] | 产品路线列表，≥ 1 |
| `pain_points` | list[dict] | 痛点列表 |

## competitors[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `asin` | string | ASIN 编号 |
| `title` | string | 产品标题 |
| `brand` | string | 品牌 |
| `price` | number\|null | 价格 |
| `monthly_sales` | number\|null | 月销量 |
| `rating` | number\|null | 评分 |
| `rating_count` | number\|null | 评论数 |
| `route_id` | string | 所属路线 route_id |

## product_routes[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `route_id` | string | kebab-case 路线标识 |
| `route_name` | string | 中文路线名 |
| `market_demand` | int\|null | 市场需求评分 0-100 |
| `competition` | int\|null | 竞争评分 0-100 |
| `price_profit` | int\|null | 价格带机会评分 0-100 |
| `voc_opportunity` | int\|null | VOC 机会评分 0-100 |
| `risk` | int\|null | 风险评分 0-100 |
| `data_quality` | int\|null | 数据质量评分 0-100 |

## keywords[] 每条必填

| 字段 | 类型 | 说明 |
|------|------|------|
| `keyword` | string | 关键词文本 |
| `role` | string | 关键词角色（如 主攻词/测试词/否定词） |

## XLSX 关键字段（Stage 12 校验阻断依据）

`validate_report_data_completeness.py` 检查以下字段是否存在且非空：

| 节 | 检查字段 |
|----|----------|
| `competitors` | asin, price, monthly_sales, rating, rating_count |
| `keywords` | keyword, role |
| `product_routes` | route_name, market_demand, competition |
| `pain_points` | dimension, priority |

空值率 > 30% → FAIL，阻断 Stage 13 XLSX 生成。

## 禁止事项

- Report Generation Agent **不新增证据包外数字**，所有数据必须从 seed + judgment + 证据包转录
- `report_data.json` 必须输出到 `analysis/` 目录，不能放到 run 根目录
- 判断类字段（final_verdict 等）从 integrated_operator_judgment.json 转录，不自创
