#!/usr/bin/env python3
"""Build an IP/compliance screening template for manual review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.report_renderer.render_report import _write_xlsx


IP_ENTRIES = [
    ("外观专利", "产品形状、结构、图案、包装外观高度相似", "WIPO 外观设计", "https://designdb.wipo.int/designdb/en/index.jsp"),
    ("外观专利", "美国站外观风险", "USPTO Patent Public Search", "https://ppubs.uspto.gov/pubwebapp/static/pages/landing.html"),
    ("外观专利", "欧盟外观风险", "EUIPO DesignView", "https://www.tmdn.org/tmdsview-web/welcome"),
    ("实用/发明专利", "核心功能、连接方式、使用方法、内部结构可能被保护", "WIPO 专利", "https://patentscope.wipo.int/"),
    ("实用/发明专利", "美国站专利风险", "USPTO Patent Public Search", "https://ppubs.uspto.gov/pubwebapp/static/pages/landing.html"),
    ("实用/发明专利", "欧洲专利风险", "EPO Espacenet", "https://worldwide.espacenet.com/"),
    ("商标", "标题、五点、A+、图片里出现品牌词、功能词、型号词、图案词", "WIPO 全球品牌库", "https://branddb.wipo.int/"),
    ("商标", "美国站商标风险", "USPTO 商标", "https://tmsearch.uspto.gov/"),
    ("商标", "欧盟商标风险", "EUIPO TMview", "https://www.tmdn.org/tmview/"),
    ("版权", "图片、图案、IP 形象、说明书、A+ 文案可能复制他人作品", "美国版权目录", "https://cocatalog.loc.gov/"),
    ("中国供应链参考", "供应链端专利/商标参考", "中国 CNIPA 专利检索", "http://pss-system.cnipa.gov.cn/"),
    ("中国供应链参考", "供应链端商标参考", "中国商标网", "http://wcjs.sbj.cnipa.gov.cn/"),
]


COMPLIANCE_RULES = [
    {
        "trigger_field": "is_children_product",
        "label": "儿童用品/玩具",
        "us_materials": "CPSC、CPC、CPSIA、ASTM F963",
        "eu_uk_materials": "CE 玩具安全、EN71、UKCA",
        "status": "强制前置判断",
        "entries": "CPSC 产品规则；CPSC Regulatory Robot；CPSC Children's Product Certificate",
    },
    {
        "trigger_field": "is_general_consumer_product",
        "label": "普通受 CPSC 规则约束消费品",
        "us_materials": "GCC、对应产品规则",
        "eu_uk_materials": "GPSR 或品类安全规则",
        "status": "需查适用标准",
        "entries": "CPSC 产品规则；CPSC General Certificate of Conformity",
    },
    {
        "trigger_field": "has_electric",
        "label": "带电/电子产品",
        "us_materials": "FCC、UL/ETL/NRTL、能效",
        "eu_uk_materials": "CE、EMC、LVD、RoHS、UKCA",
        "status": "前置判断",
        "entries": "FCC Equipment Authorization；FCC Equipment Authorization System",
    },
    {
        "trigger_field": "has_wireless_rf",
        "label": "蓝牙/Wi-Fi/遥控/RF",
        "us_materials": "FCC Certification / SDoC、FCC ID",
        "eu_uk_materials": "RED、CE、UKCA",
        "status": "前置判断",
        "entries": "FCC Equipment Authorization",
    },
    {
        "trigger_field": "has_battery",
        "label": "锂电池/含电池",
        "us_materials": "UN38.3、MSDS/SDS、UL 相关测试、运输要求",
        "eu_uk_materials": "UN38.3、RoHS、Battery Regulation",
        "status": "前置判断",
        "entries": "FCC/CPSC/运输材料按产品属性复核",
    },
    {
        "trigger_field": "is_food_contact",
        "label": "食品接触材料/厨房用品",
        "us_materials": "FDA food contact、Prop 65",
        "eu_uk_materials": "LFGB、EU food contact、REACH",
        "status": "前置判断",
        "entries": "FDA Packaging & Food Contact Substances",
    },
    {
        "trigger_field": "is_skin_contact_liquid",
        "label": "化妆品/护肤/接触皮肤液体",
        "us_materials": "FDA 标签、MoCRA、成分和安全证明",
        "eu_uk_materials": "EU Cosmetics Regulation、UK cosmetic rules",
        "status": "高风险品类",
        "entries": "FDA 相关入口；EU Cosmetics 规则",
    },
    {
        "trigger_field": "has_medical_health_claim",
        "label": "医疗/健康宣称",
        "us_materials": "FDA medical device / OTC 风险",
        "eu_uk_materials": "MDR/UK medical device 风险",
        "status": "谨慎或避开",
        "entries": "FDA medical device / OTC 相关入口",
    },
    {
        "trigger_field": "has_laser_uv_led_radiation",
        "label": "激光/UV/LED/辐射产品",
        "us_materials": "FDA CDRH radiation-emitting products",
        "eu_uk_materials": "CE、相关安全标准",
        "status": "前置判断",
        "entries": "FDA Radiation-Emitting Products；FDA Radiation Product Codes",
    },
    {
        "trigger_field": "is_ppe",
        "label": "PPE/防护用品",
        "us_materials": "NIOSH/FDA/OSHA 等视产品而定",
        "eu_uk_materials": "PPE Regulation、CE/UKCA",
        "status": "高风险品类",
        "entries": "CPSC/FDA/OSHA/NIOSH 按具体产品复核",
    },
]


OFFICIAL_LINKS = [
    ("CPSC 产品规则", "https://www.cpsc.gov/Business--Manufacturing/International/Topics/Regulations-Laws-and-Information-by-Product-for-Manufacturers-Importers-Distributors-and-Retailers"),
    ("CPSC Regulatory Robot", "https://business.cpsc.gov/robot/"),
    ("CPSC 测试与认证", "https://www.cpsc.gov/Business--Manufacturing/Testing-Certification/"),
    ("CPSC Children's Product Certificate", "https://www.cpsc.gov/Business--Manufacturing/Testing-Certification/Childrens-Product-Certificate"),
    ("CPSC General Certificate of Conformity", "https://www.cpsc.gov/Business--Manufacturing/Testing-Certification/General-Certificate-of-Conformity"),
    ("CPSC 认可实验室", "https://business.cpsc.gov/cgi-bin/labsearch/Default.aspx"),
    ("FCC Equipment Authorization", "https://www.fcc.gov/general/equipment-authorization-procedures"),
    ("FCC Equipment Authorization System", "https://www.fcc.gov/laboratory-division/equipment-authorization-approval-guide/equipment-authorization-system"),
    ("FDA Packaging & Food Contact Substances", "https://www.fda.gov/food/food-ingredients-packaging/packaging-food-contact-substances-fcs"),
    ("FDA Radiation-Emitting Products", "https://www.fda.gov/radiation-emitting-products"),
    ("FDA Radiation Product Codes", "https://www.fda.gov/radiation-emitting-products/performance-standards-radiological-health-program/product-codes-radiation-emitting-electronic-products"),
    ("EU CE Marking", "https://europa.eu/youreurope/business/product-requirements/labels-markings/ce-marking/index_en.htm"),
]


PRODUCT_FLAG_FIELDS = [
    ("target_market", "目标市场", "US"),
    ("product_usage", "产品用途", ""),
    ("user_group", "使用人群", "成人/宠物/儿童"),
    ("material_coating", "材质和涂层", ""),
    ("package_instruction_plan", "包装和说明书计划", ""),
    ("is_children_product", "是否儿童用品/玩具", "否"),
    ("is_general_consumer_product", "是否一般消费品", "是"),
    ("has_electric", "是否带电/电子", "否"),
    ("has_wireless_rf", "是否带无线/RF", "否"),
    ("has_battery", "是否含电池", "否"),
    ("is_food_contact", "是否接触食品", "否"),
    ("is_skin_contact_liquid", "是否接触皮肤/入口/眼睛/液体", "否"),
    ("has_medical_health_claim", "是否有医疗/治疗/健康/安全/防护宣称", "否"),
    ("has_laser_uv_led_radiation", "是否含激光/UV/LED/辐射", "否"),
    ("has_heat_pressure_moving_parts", "是否有加热/压力/运动部件", "否"),
    ("is_ppe", "是否 PPE/防护用品", "否"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build IP/compliance screening template from research_package.json.")
    parser.add_argument("research_package_json")
    parser.add_argument("output_xlsx")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package = json.loads(Path(args.research_package_json).expanduser().resolve().read_text(encoding="utf-8"))
    output_path = Path(args.output_xlsx).expanduser().resolve()
    render_ip_compliance_template(package, output_path)
    print(f"Wrote IP/compliance template: {output_path}")
    return 0


def render_ip_compliance_template(package: dict[str, Any], output_path: Path) -> None:
    _write_xlsx(
        output_path,
        [
            ("填写说明", instruction_rows(package)),
            ("产品属性", product_flag_rows(package)),
            ("知产初筛", ip_screening_rows(package)),
            ("合规初筛", compliance_screening_rows(package)),
            ("检索入口", link_rows()),
            ("合规规则", compliance_rule_rows()),
        ],
    )


def instruction_rows(package: dict[str, Any]) -> list[list[Any]]:
    meta = package.get("metadata", {})
    return [
        ["项", "值"],
        ["候选方向", meta.get("seed_keyword_or_category", "")],
        ["站点", meta.get("site", "")],
        ["边界", "AI 只生成初筛清单和回填报告，不替代律师、专利代理机构、检测机构或 Amazon 合规团队结论。"],
        ["填写方式", "人工到模板推荐的网站检索后，填写 result、evidence_link、evidence_note、next_step。"],
        ["风险等级", "可填：低 / 中 / 高 / 强风险 / 待复核。"],
    ]


def product_flag_rows(package: dict[str, Any]) -> list[list[Any]]:
    meta = package.get("metadata", {})
    rows = [["field", "label", "value", "note"]]
    for field, label, default in PRODUCT_FLAG_FIELDS:
        value = default
        if field == "target_market":
            value = meta.get("site") or default
        rows.append([field, label, value, "人工复核；缺少关键属性时不能写合规低风险。"])
    return rows


def ip_screening_rows(package: dict[str, Any]) -> list[list[Any]]:
    keyword = package.get("metadata", {}).get("seed_keyword_or_category", "")
    candidate_keywords = suggested_keywords(package)
    rows = [["risk_type", "trigger_reason", "search_entry", "search_url", "suggested_keywords", "result", "evidence_link", "evidence_note", "next_step"]]
    for risk_type, reason, entry, url in IP_ENTRIES:
        rows.append([risk_type, reason, entry, url, candidate_keywords or keyword, "", "", "", "人工初筛后填写：继续/人工复核/专业复核/淘汰"])
    return rows


def compliance_screening_rows(package: dict[str, Any]) -> list[list[Any]]:
    rows = [["trigger_field", "product_attribute", "us_possible_materials", "eu_uk_possible_materials", "early_status", "recommended_entries", "result", "evidence_link", "evidence_note", "next_step"]]
    for rule in COMPLIANCE_RULES:
        rows.append(
            [
                rule["trigger_field"],
                rule["label"],
                rule["us_materials"],
                rule["eu_uk_materials"],
                rule["status"],
                rule["entries"],
                "",
                "",
                "",
                "人工确认产品属性和可能材料后填写",
            ]
        )
    return rows


def link_rows() -> list[list[Any]]:
    rows = [["name", "url"]]
    for _, _, entry, url in IP_ENTRIES:
        rows.append([entry, url])
    for name, url in OFFICIAL_LINKS:
        rows.append([name, url])
    return rows


def compliance_rule_rows() -> list[list[Any]]:
    rows = [["产品属性", "美国常见可能材料", "欧盟/英国常见可能材料", "早期判断"]]
    for rule in COMPLIANCE_RULES:
        rows.append([rule["label"], rule["us_materials"], rule["eu_uk_materials"], rule["status"]])
    return rows


def suggested_keywords(package: dict[str, Any]) -> str:
    meta = package.get("metadata", {})
    competitors = package.get("competitor_pool", {})
    parts = [str(meta.get("seed_keyword_or_category", "") or "")]
    for item in competitors.get("top10", [])[:5]:
        for key in ("brand", "asin"):
            value = item.get(key)
            if value:
                parts.append(str(value))
    return "；".join(dict.fromkeys(part for part in parts if part))


if __name__ == "__main__":
    raise SystemExit(main())
