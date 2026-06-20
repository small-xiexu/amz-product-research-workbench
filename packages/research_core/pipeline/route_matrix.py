"""Product route matrix — splitting market candidates into product routes."""

from __future__ import annotations

import re
from typing import Any

from packages.research_core.pipeline.market_text import _fmt_number, _positive_count
from packages.research_core.pipeline.market_boundary import _market_anchor_terms, _competitor_market_relevance
from packages.research_core.pipeline.shared import _dedupe_strings, _TITLE_NOISE_TOKENS


PRODUCT_ROUTE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "route_id": "base_core",
        "route_name": "基础款：核心形态 / 标准配置",
        "route_type": "主线",
        "priority": 10,
        "always_consider": True,
        "match_terms": ("基础", "标准", "basic", "standard", "classic"),
        "competitor_terms": ("basic", "standard", "classic"),
        "review_terms": ("basic", "standard", "easy to use", "fit", "quality", "基础", "标准", "好用", "质量"),
        "route_search_terms": ["{candidate_name} 基础款", "{candidate_name} 标准款"],
        "seller_sprite_exports": [
            "用主关键词导出搜索结果、市场分析 Top100 和 ABA。",
            "挑 3-5 个标准形态 ASIN 做关键词反查，看真实成交词是不是目标场景。",
        ],
        "sorftime_checks": [
            "keyword_detail：主关键词和 1-2 个标准形态长尾词。",
            "product_traffic_terms：基础款 Top3 ASIN，确认它们靠什么词拿流量。",
        ],
        "opportunity": "先建立主线基准，看这个品类最常见、最容易量产的标准形态是否值得进入样品验证。",
        "risks": "标准款往往同质化强，不能只看低价；要确认差评是否集中在质量、尺寸、稳定性或使用体验。",
        "validation_actions": [
            "补标准形态代表 ASIN、关键词反查和评论 VOC，确认基础需求是否真实存在。",
            "把最容易差评的基础体验转成后续产品验证点：尺寸、稳定性、耐用性和使用门槛。",
        ],
        "decision_gate": [
            "标准形态能解决核心使用痛点。",
            "主关键词与目标形态一致，不是被泛词或混池词带偏。",
        ],
        "decision_hint": "作为主推基准款观察，但必须和升级款/场景款一起比较需求、评论门槛和差异化。",
    },
    {
        "route_id": "upgraded_core",
        "route_name": "升级款：更高客单价 / 更强功能配置",
        "route_type": "升级",
        "priority": 20,
        "always_consider": True,
        "match_terms": (
            "升级",
            "高配",
            "加强",
            "加厚",
            "重型",
            "专业",
            "premium",
            "upgraded",
            "heavy duty",
            "reinforced",
            "pro",
        ),
        "competitor_terms": ("premium", "upgraded", "heavy duty", "reinforced", "pro"),
        "review_terms": ("premium", "upgraded", "durable", "sturdy", "heavy duty", "加强", "耐用", "结实"),
        "route_search_terms": ["{candidate_name} 升级款", "{candidate_name} 高配", "{candidate_name} 加强"],
        "seller_sprite_exports": [
            "用升级/高配/专业款长尾词补搜索结果和关键词反查。",
            "单独拉升级款竞品 ASIN，不和标准款混在同一批 VOC 里判断。",
        ],
        "sorftime_checks": [
            "keyword_detail：升级款/高配款长尾词。",
            "product_traffic_terms：升级款代表 ASIN，确认是否有独立成交流量。",
            "competitor_product_keywords：看升级款是否避开纯低价竞争。",
        ],
        "opportunity": "升级款通常更适合做差异化和客单价，需要单独看是否真的有需求，而不是只把它当标题或图片里的一个规格。",
        "risks": "升级配置如果只是标题词或图片装饰，样品不达标会直接变成差评；成本也容易被低估。",
        "validation_actions": [
            "把标准款和升级款分别拉代表 ASIN，看升级点是否有独立需求和转化词。",
            "用评论证据单独验证升级点：强度、材质、结构、配件和实际使用差异。",
        ],
        "decision_gate": [
            "升级点有独立竞品、独立需求词或明确 VOC 痛点承接。",
            "升级路线有独立关键词、竞品或评论痛点承接。",
            "升级后价格带仍有销量和低评论切入口。",
        ],
        "decision_hint": "不要混在标准款里看；作为升级路线单独算成本、售价和样品测试。",
    },
    {
        "route_id": "scenario_specialized",
        "route_name": "场景款：明确使用场景 / 人群",
        "route_type": "场景",
        "priority": 30,
        "always_consider": True,
        "match_terms": (
            "户外",
            "旅行",
            "车载",
            "厨房",
            "浴室",
            "儿童",
            "宠物",
            "露营",
            "办公",
            "outdoor",
            "travel",
            "car",
            "shower",
            "kitchen",
            "camping",
            "office",
        ),
        "competitor_terms": ("outdoor", "travel", "car", "shower", "kitchen", "camping", "office"),
        "review_terms": ("outdoor", "travel", "car", "shower", "kitchen", "场景", "户外", "旅行", "汽车", "浴室"),
        "route_search_terms": ["{candidate_name} 场景款", "{candidate_name} 户外", "{candidate_name} 家用"],
        "seller_sprite_exports": [
            "按场景词补搜索结果，不和泛品类词混在一起看。",
            "为每个高潜场景挑 2-3 个代表 ASIN 做关键词反查。",
        ],
        "sorftime_checks": [
            "keyword_detail：场景词 + 品类词。",
            "product_traffic_terms：场景款代表 ASIN，确认它是否真靠场景词成交。",
        ],
        "opportunity": "场景款能避开纯泛词竞争，适合寻找更清晰的人群、用途和页面卖点。",
        "risks": "场景不清会把不同需求混在一起，导致 VOC、关键词和竞品判断互相拉偏。",
        "validation_actions": [
            "确认这个场景有独立关键词、独立竞品和独立评论痛点。",
            "样品要按真实使用场景测试，而不是只看标题是否写了场景词。",
        ],
        "decision_gate": [
            "场景词有搜索量或竞品流量支撑。",
            "评论证据能证明该场景存在未满足需求。",
            "页面和评论证据能解释该场景为什么需要不同结构、材质或包装方案。",
        ],
        "decision_hint": "适合作为副主线观察；若证据强，可升级为主推路线。",
    },
    {
        "route_id": "bundle_or_set",
        "route_name": "组合/套装款：多件套 / 可替换配件",
        "route_type": "组合",
        "priority": 40,
        "always_consider": True,
        "match_terms": (
            "套装",
            "组合",
            "多件套",
            "两件套",
            "三件套",
            "替换",
            "配件",
            "set",
            "kit",
            "combo",
            "bundle",
            "replacement",
            "2 in 1",
            "3 in 1",
            "二合一",
            "三合一",
        ),
        "competitor_terms": ("set", "kit", "combo", "bundle", "replacement", "2 in 1", "3 in 1"),
        "review_terms": ("set", "kit", "replacement", "parts", "bundle", "套装", "替换", "配件", "组合"),
        "route_search_terms": ["{candidate_name} 套装", "{candidate_name} 组合", "{candidate_name} 替换件"],
        "seller_sprite_exports": [
            "用 kit / set / replacement 等组合词补搜索结果和关键词反查。",
            "把套装款和单品款分开看价格带、评论门槛和退货风险。",
        ],
        "sorftime_checks": [
            "keyword_detail：套装/组合/替换件长尾词。",
            "product_traffic_terms：套装代表 ASIN，确认套装是否带来独立流量。",
        ],
        "opportunity": "组合/套装有机会提高客单价或降低同质化，但必须确认买家是真的需要整套，而不是随便打包。",
        "risks": "套装会增加重量、缺件、包装和退货风险；不能只看套装看起来更丰富。",
        "validation_actions": [
            "单独看套装款代表 ASIN 的价格带、评论门槛和关键词入口。",
            "从评论里确认缺件、包装保护、替换件兼容性和说明书是否是高频风险。",
        ],
        "decision_gate": [
            "套装有独立需求词或评论痛点支撑。",
            "套装价格带有销量，并且低评论样本不是偶然个案。",
            "评论和竞品证据能证明整套配件有真实需求。",
        ],
        "decision_hint": "不要只因看起来更丰富就选套装；先把成本和缺件风险算清。",
    },
    {
        "route_id": "feature_material_upgrade",
        "route_name": "功能/材质升级：安全、耐用、专业化卖点",
        "route_type": "功能升级",
        "priority": 50,
        "always_consider": True,
        "match_terms": (
            "防滑",
            "防水",
            "防摔",
            "反光",
            "可伸缩",
            "折叠",
            "旋转",
            "加固",
            "耐用",
            "铝合金",
            "不锈钢",
            "硅胶",
            "微纤维",
            "waterproof",
            "non slip",
            "reflective",
            "foldable",
            "extendable",
            "telescopic",
            "rotating",
            "reinforced",
            "stainless",
            "microfiber",
        ),
        "competitor_terms": ("waterproof", "reflective", "foldable", "extendable", "reinforced", "stainless", "microfiber"),
        "review_terms": ("durable", "sturdy", "waterproof", "slip", "break", "耐用", "结实", "防滑", "断", "坏"),
        "route_search_terms": ["{candidate_name} 加强", "{candidate_name} 防滑", "{candidate_name} 耐用"],
        "seller_sprite_exports": [
            "不用一开始单独拉大盘，先放进主线/升级款竞品反查里看功能词。",
            "若功能词有明显流量，再单独补搜索结果和关键词反查。",
        ],
        "sorftime_checks": [
            "keyword_extends：查功能/材质长尾词。",
            "similar_product_feature：选定主路线后再看热销品共有功能点。",
        ],
        "opportunity": "功能/材质升级能转成页面卖点，也能解释为什么比低价款贵。",
        "risks": "这些升级如果只停留在标题词，样品不达标反而更容易被差评打回来。",
        "validation_actions": [
            "把功能/材质升级写成可验证规格，并回到代表 ASIN、评论和页面卖点核对。",
            "按差评痛点设计后续验证问题，确认升级点不是标题装饰词。",
        ],
        "decision_gate": [
            "功能升级能承接真实 VOC 痛点。",
            "升级点有图片/视频/样品证据，而不是标题词。",
            "升级后成本、重量和售后风险可控。",
        ],
        "decision_hint": "适合作为基础/升级路线的必验卖点，证据强时再独立成路线。",
    },
    {
        "route_id": "adjacent_or_watch",
        "route_name": "旁支观察：相近形态 / 混池候选",
        "route_type": "观察",
        "priority": 90,
        "match_terms": ("旁支", "混池", "相近", "待确认", "不明确", "其他", "adjacent", "similar"),
        "competitor_terms": (),
        "review_terms": (),
        "route_search_terms": ["{candidate_name} 相似款", "{candidate_name} 替代款"],
        "seller_sprite_exports": [
            "只在主线/升级路线证据不足时补旁支数据。",
            "旁支候选必须单独标记，不能混进主推款评分。",
        ],
        "sorftime_checks": [
            "keyword_extends：确认旁支词是否只是混池，还是有独立需求。",
        ],
        "opportunity": "可能有可借鉴结构、低价供给或备用方向，可留作观察。",
        "risks": "相近不等于目标产品，混进去会拉偏 VOC、关键词和竞品判断。",
        "validation_actions": [
            "打开详情确认它和目标形态的关键差异。",
            "证据不足时只留观察，不进入主推评分。",
        ],
        "decision_gate": [
            "确认它不是主线/升级路线的低质量混池。",
            "若要升级为主线，必须补独立需求、关键词、竞品和 VOC 证据。",
        ],
        "decision_hint": "先观察，不抢主线资源；证据变强后再升级。",
    },
)


def _route_evidence_plain_summary(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return "路线矩阵还没形成，下一步先按大类、小类、关键词和代表 ASIN 拆路线。"
    strong = [route for route in routes if _positive_count(route.get("competitor_count")) or _positive_count(route.get("candidate_count"))]
    return f"已拆出 {len(routes)} 条路线，其中 {len(strong)} 条有代表竞品或市场样本；下一步按路线补关键词和 VOC，而不是用一个泛词判断全部市场。"



def _build_product_route_matrix(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    review: dict[str, Any] = {}
    profile = _route_profile(candidate, review)
    context = _build_product_context(candidate, review, profile)
    definitions = [
        _route_definition_with_context(definition, context, profile, candidate)
        for definition in PRODUCT_ROUTE_DEFINITIONS
    ]
    route_buckets = {definition["route_id"]: [] for definition in PRODUCT_ROUTE_DEFINITIONS}
    for group_key, group_label in (("priority_candidates", "优先联系"), ("watchlist_candidates", "观察待核")):
        items = review.get(group_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_with_group = {**item, "route_source_group": group_label}
            for route_id in _classify_market_route(item_with_group, definitions):
                route_buckets.setdefault(route_id, []).append(item_with_group)

    if not any(route_buckets.values()):
        for item in _market_route_reference_items(candidate):
            item_route_ids = _classify_market_route(item, definitions)
            for route_id in item_route_ids:
                route_buckets.setdefault(route_id, []).append(item)

    routes: list[dict[str, Any]] = []
    for definition in definitions:
        items = route_buckets.get(definition["route_id"], [])
        if not items and not definition.get("always_consider"):
            continue
        price_min, price_max = _route_price_range(_route_price_items(items))
        priority_count = sum(1 for item in items if item.get("route_source_group") == "优先联系")
        watchlist_count = sum(1 for item in items if item.get("route_source_group") == "观察待核")
        route_keywords = _route_keyword_hints(candidate, definition)
        routes.append(
            {
                "route_id": definition["route_id"],
                "route_name": definition["route_name"],
                "route_type": definition["route_type"],
                "route_profile": context.get("profile_id", "runtime"),
                "product_context": context,
                "route_keywords": route_keywords,
                "always_consider": bool(definition.get("always_consider")),
                "match_terms": list(definition.get("match_terms", [])),
                "require_any_terms": list(definition.get("require_any_terms", [])),
                "competitor_terms": list(definition.get("competitor_terms", [])),
                "review_terms": list(definition.get("review_terms", [])),
                "seller_sprite_exports": list(definition.get("seller_sprite_exports", [])),
                "sorftime_checks": list(definition.get("sorftime_checks", [])),
                "route_search_terms": list(definition.get("route_search_terms", [])),
                "decision_gate": list(definition.get("decision_gate", [])),
                "candidate_count": len(items),
                "competitor_count": len(items),
                "priority_count": priority_count,
                "watchlist_count": watchlist_count,
                "price_usd_min": price_min,
                "price_usd_max": price_max,
                "price_text": _route_price_text(price_min, price_max),
                "representative_items": [_route_item_summary(item) for item in items[:3]],
                "opportunity": definition["opportunity"],
                "risks": definition["risks"],
                "validation_actions": definition["validation_actions"],
                "decision_hint": definition["decision_hint"],
            }
        )
    routes.sort(key=lambda item: _route_priority(item.get("route_id")))
    return routes



def _route_profile(candidate: dict[str, Any], review: dict[str, Any], route_signal: dict[str, Any] | None = None) -> dict[str, Any]:
    profile_sources = [
        candidate.get("product_route_profile"),
        candidate.get("route_profile"),
        (candidate.get("product_context") or {}).get("route_profile") if isinstance(candidate.get("product_context"), dict) else None,
        (route_signal or {}).get("product_route_profile") if isinstance(route_signal, dict) else None,
        review.get("product_route_profile") if isinstance(review, dict) else None,
    ]
    for profile in profile_sources:
        if isinstance(profile, dict):
            return profile
    return {"profile_id": "runtime_inferred", "route_overrides": {}}



def _route_definition_with_context(
    definition: dict[str, Any],
    context: dict[str, Any],
    profile: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    route_id = str(definition.get("route_id") or "")
    overrides = profile.get("route_overrides") if isinstance(profile.get("route_overrides"), dict) else {}
    override = overrides.get(route_id) if isinstance(overrides.get(route_id), dict) else {}
    merged: dict[str, Any] = dict(definition)
    inferred = _inferred_route_overrides(route_id, context)
    for key, value in inferred.items():
        merged[key] = value
    for key, value in override.items():
        if key in {"match_terms", "require_any_terms", "competitor_terms", "review_terms", "route_search_terms"}:
            merged[key] = _dedupe_strings([str(item) for item in value]) if isinstance(value, (list, tuple)) else value
        else:
            merged[key] = value
    merged["route_search_terms"] = _format_route_terms(merged.get("route_search_terms", []), candidate)
    return merged



def _route_definition_index(route_id: str) -> int:
    for index, definition in enumerate(PRODUCT_ROUTE_DEFINITIONS):
        if definition.get("route_id") == route_id:
            return index
    return 0



def _build_product_context(
    candidate: dict[str, Any],
    review: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    explicit = candidate.get("product_context") if isinstance(candidate.get("product_context"), dict) else {}
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    core_terms = _context_terms_from_values(
        explicit.get("core_terms"),
        explicit.get("product_terms"),
        candidate.get("name"),
        demand.get("top_keyword"),
        demand.get("aba_top_search_term"),
    )
    route_terms = {
        "base_core": _context_terms_from_values(explicit.get("base_terms"), explicit.get("standard_terms")),
        "upgraded_core": _context_terms_from_values(explicit.get("upgrade_terms"), explicit.get("premium_terms")),
        "scenario_specialized": _context_terms_from_values(explicit.get("scenario_terms"), explicit.get("audience_terms")),
        "bundle_or_set": _context_terms_from_values(explicit.get("bundle_terms"), explicit.get("set_terms")),
        "feature_material_upgrade": _context_terms_from_values(explicit.get("feature_terms"), explicit.get("material_terms")),
        "adjacent_or_watch": _context_terms_from_values(explicit.get("adjacent_terms"), explicit.get("exclude_terms")),
    }
    for item in _route_source_items(candidate, review):
        text = _route_item_text(item)
        for route_id in route_terms:
            terms = _extract_route_terms_from_text(route_id, text)
            if terms:
                route_terms[route_id].extend(terms)
        title = item.get("title")
        if title:
            core_terms.extend(_meaningful_title_terms(str(title), limit=4))
    for item in _competitor_source_items(candidate):
        title = str(item.get("title") or "")
        for route_id in route_terms:
            terms = _extract_route_terms_from_text(route_id, title.lower())
            if terms:
                route_terms[route_id].extend(terms)
    profile_terms = profile.get("route_terms") if isinstance(profile.get("route_terms"), dict) else {}
    for route_id, terms in profile_terms.items():
        route_terms.setdefault(str(route_id), []).extend(_context_terms_from_values(terms))
    core_terms = _dedupe_strings([term for term in core_terms if _is_meaningful_context_term(term)])[:8]
    if not core_terms:
        core_terms = ["目标产品"]
    clean_route_terms = {
        route_id: _dedupe_strings([term for term in terms if _is_meaningful_context_term(term)])[:8]
        for route_id, terms in route_terms.items()
    }
    return {
        "profile_id": str(profile.get("profile_id") or "runtime_inferred"),
        "core_terms": core_terms,
        "route_terms": clean_route_terms,
        "exclude_terms": _context_terms_from_values(explicit.get("exclude_terms"), profile.get("exclude_terms")),
    }



def _inferred_route_overrides(route_id: str, context: dict[str, Any]) -> dict[str, Any]:
    core_terms = _context_route_terms(context, "core_terms")
    route_terms = _context_route_terms(context, route_id)
    evidence_terms = _dedupe_strings(route_terms or (core_terms if route_id == "base_core" else []))
    if not core_terms:
        core_terms = ["目标产品"]
    title = _route_name_from_context(route_id, core_terms, route_terms)
    search_terms = _route_search_terms(route_id, core_terms, route_terms)
    checks = _route_sorftime_checks(route_id, core_terms, route_terms)
    exports = _route_seller_sprite_exports(route_id, core_terms, route_terms)
    result: dict[str, Any] = {
        "route_name": title,
        "match_terms": _dedupe_strings(list(PRODUCT_ROUTE_DEFINITIONS[_route_definition_index(route_id)].get("match_terms", ())) + route_terms),
        "competitor_terms": evidence_terms,
        "review_terms": evidence_terms,
        "route_search_terms": search_terms,
        "seller_sprite_exports": exports,
        "sorftime_checks": checks,
    }
    return result



def _context_terms_from_values(*values: Any) -> list[str]:
    terms: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            terms.extend(_context_terms_from_values(*value.values()))
            continue
        if isinstance(value, (list, tuple, set)):
            terms.extend(_context_terms_from_values(*value))
            continue
        text = re.sub(r"\s+", " ", str(value)).strip()
        if not text:
            continue
        parts = re.split(r"[,，;；、\n\t|]+", text)
        for part in parts:
            clean = part.strip(" -_/")
            if clean:
                terms.append(clean)
    return _dedupe_strings(terms)



def _route_source_items(candidate: dict[str, Any], review: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ("priority_candidates", "watchlist_candidates", "visual_review_queue"):
        value = review.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items[:30]



def _competitor_source_items(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    groups = candidate.get("competitor_candidates", {})
    if not isinstance(groups, dict):
        return []
    items: list[dict[str, Any]] = []
    for key in ("top10", "recent_winners", "structure_supplement"):
        value = groups.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items[:30]



def _extract_route_terms_from_text(route_id: str, text: str) -> list[str]:
    definition = PRODUCT_ROUTE_DEFINITIONS[_route_definition_index(route_id)]
    terms = []
    for term in definition.get("match_terms", ()):
        clean = str(term).strip()
        if clean and clean.lower() in text.lower():
            terms.append(clean)
    return _dedupe_strings(terms)



def _meaningful_title_terms(text: str, limit: int = 4) -> list[str]:
    raw_parts = re.split(r"[,，;；、\n\t|()（）\\[\\]{}]+", text)
    parts: list[str] = []
    for raw in raw_parts:
        chunk = re.sub(r"\s+", " ", raw).strip(" -_/")
        if not chunk:
            continue
        tokens = chunk.split()
        if len(tokens) > 1:
            phrase = " ".join(token for token in tokens if token.lower() not in _TITLE_NOISE_TOKENS)
            if _is_meaningful_context_term(phrase):
                parts.append(phrase)
            continue
        if chunk.lower() not in _TITLE_NOISE_TOKENS and _is_meaningful_context_term(chunk):
            parts.append(chunk)
    return _dedupe_strings(parts)[:limit]



def _is_meaningful_context_term(term: Any) -> bool:
    text = re.sub(r"\s+", " ", str(term or "")).strip()
    if len(text) < 2 or len(text) > 80:
        return False
    if re.fullmatch(r"[\d\s._-]+", text):
        return False
    return True



def _context_route_terms(context: dict[str, Any], route_id: str) -> list[str]:
    if route_id == "core_terms":
        value = context.get("core_terms")
        return list(value) if isinstance(value, list) else []
    routes = context.get("route_terms")
    if isinstance(routes, dict):
        value = routes.get(route_id)
        return list(value) if isinstance(value, list) else []
    return []



def _route_name_from_context(route_id: str, core_terms: list[str], route_terms: list[str]) -> str:
    term_text = _short_route_term_text(route_terms or core_terms[:1])
    if route_id == "base_core":
        return f"基础款：{term_text} / 标准配置"
    if route_id == "upgraded_core":
        return f"升级款：{term_text or '更高客单价 / 更强功能配置'}"
    if route_id == "scenario_specialized":
        return f"场景款：{term_text or '明确使用场景 / 人群'}"
    if route_id == "bundle_or_set":
        return f"组合/套装款：{term_text or '多件套 / 可替换配件'}"
    if route_id == "feature_material_upgrade":
        return f"功能/材质升级：{term_text or '安全、耐用、专业化卖点'}"
    if route_id == "adjacent_or_watch":
        return f"旁支观察：{term_text or '相近形态 / 混池候选'}"
    return term_text or str(route_id)



def _short_route_term_text(terms: list[str]) -> str:
    clean = [str(term).strip() for term in terms if _is_meaningful_context_term(term)]
    return " + ".join(clean[:3])



def _route_search_terms(route_id: str, core_terms: list[str], route_terms: list[str]) -> list[str]:
    suffix = {
        "base_core": "基础款",
        "upgraded_core": "升级款",
        "scenario_specialized": "场景款",
        "bundle_or_set": "套装",
        "feature_material_upgrade": "加强",
        "adjacent_or_watch": "相似款",
    }.get(route_id, "")
    terms: list[str] = []
    for core in core_terms[:3]:
        if suffix:
            terms.append(f"{core} {suffix}")
        for route_term in route_terms[:3]:
            if route_term.lower() not in core.lower():
                terms.append(f"{core} {route_term}")
    if not terms:
        terms = [f"{core_terms[0]} {suffix}".strip()]
    return _dedupe_strings(terms)[:6]



def _route_seller_sprite_exports(route_id: str, core_terms: list[str], route_terms: list[str]) -> list[str]:
    route_label = _route_name_from_context(route_id, core_terms, route_terms)
    keyword_hint = " / ".join(_dedupe_strings(route_terms[:2] + core_terms[:2])) or "主关键词"
    return [
        f"用 {keyword_hint} 导出搜索结果、市场分析 Top100 和 ABA。",
        f"为「{route_label}」挑 3-5 个代表 ASIN 做关键词反查，不和其它路线混在同一批判断。",
    ]



def _route_sorftime_checks(route_id: str, core_terms: list[str], route_terms: list[str]) -> list[str]:
    keyword_hint = "、".join(_dedupe_strings(route_terms[:2] + core_terms[:2])) or "主关键词"
    return [
        f"keyword_detail：{keyword_hint}。",
        "product_traffic_terms：该路线代表 ASIN，确认真实成交流量词。",
        "competitor_product_keywords：看这条路线是否避开泛词低价竞争。",
    ]



def _format_route_terms(terms: Any, candidate: dict[str, Any]) -> list[str]:
    if not isinstance(terms, (list, tuple)):
        return []
    name = str(candidate.get("name") or "目标产品").strip() or "目标产品"
    clean_name = re.sub(r"[_\\-]+", " ", name).strip()
    result = []
    for term in terms:
        text = str(term).strip()
        if not text:
            continue
        result.append(text.replace("{candidate_name}", clean_name))
    return _dedupe_strings(result)



def _route_keyword_hints(candidate: dict[str, Any], definition: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    demand = candidate.get("demand_evidence", {}) if isinstance(candidate.get("demand_evidence"), dict) else {}
    for value in (
        demand.get("top_keyword"),
        demand.get("aba_top_search_term"),
        candidate.get("name"),
    ):
        if value:
            hints.append(str(value))
    for term in definition.get("route_search_terms", [])[:2]:
        hints.append(str(term))
    return _dedupe_strings(hints)[:5]



def _classify_market_route(item: dict[str, Any], definitions: list[dict[str, Any]]) -> list[str]:
    text = _route_item_text(item)
    routes: list[str] = []
    for definition in definitions:
        route_id = str(definition.get("route_id") or "")
        if not route_id:
            continue
        terms = tuple(str(term).lower() for term in definition.get("match_terms", ()) if term)
        if terms and _contains_any(text, terms) and _route_requirements_met(text, definition):
            routes.append(route_id)
    if routes:
        return _dedupe_strings(routes)
    if _looks_like_core_candidate(text):
        routes.append("base_core")
    else:
        routes.append("adjacent_or_watch")
    return _dedupe_strings(routes)



def _route_requirements_met(text: str, definition: dict[str, Any]) -> bool:
    required = tuple(str(term).lower() for term in definition.get("require_any_terms", ()) if term)
    if not required:
        return True
    return _contains_any(text, required)



def _route_item_text(item: dict[str, Any], include_review_notes: bool = True) -> str:
    fields: list[Any] = [
        item.get("title"),
        item.get("stock_text"),
        item.get("customization_text"),
        item.get("detail_summary"),
        item.get("detail_text_excerpt"),
        item.get("moq_text"),
    ]
    if include_review_notes:
        fields.append(item.get("rationale"))
    for key in ("sku_texts", "sku_options", "risk_notes"):
        value = item.get(key)
        if isinstance(value, list):
            fields.extend(value)
    return " ".join(str(field).lower() for field in fields if field not in (None, ""))



def _route_shape_text(item: dict[str, Any]) -> str:
    fields: list[Any] = [
        item.get("title"),
        item.get("stock_text"),
        item.get("moq_text"),
        item.get("customization_text"),
    ]
    for key in ("sku_texts", "sku_options"):
        value = item.get(key)
        if isinstance(value, list):
            fields.extend(value)
    return " ".join(str(field).lower() for field in fields if field not in (None, ""))



def _route_review_text(item: dict[str, Any]) -> str:
    fields: list[Any] = [item.get("rationale")]
    risks = item.get("risk_notes")
    if isinstance(risks, list):
        fields.extend(risks)
    return " ".join(str(field).lower() for field in fields if field not in (None, ""))



def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text for needle in needles)



def _looks_like_core_candidate(text: str) -> bool:
    if not text.strip():
        return False
    adjacent_terms = ("配件", "替换", "accessory", "replacement")
    if _contains_any(text, adjacent_terms):
        return False
    return True

def _route_price_range(items: list[dict[str, Any]]) -> tuple[Any, Any]:
    lows: list[float] = []
    highs: list[float] = []
    for item in items:
        low = _first_numeric(
            item.get("price_usd"),
            item.get("price"),
        )
        high = _first_numeric(
            item.get("price_usd"),
            item.get("price"),
        )
        if low is not None:
            lows.append(low)
        if high is not None:
            highs.append(high)
    return (min(lows) if lows else None, max(highs) if highs else None)



def _route_price_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority_items = [item for item in items if item.get("route_source_group") == "优先联系"]
    return priority_items or items



def _first_numeric(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, bool) or value in (None, ""):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            continue
    return None



def _route_price_text(low: Any, high: Any) -> str:
    if low is None and high is None:
        return "价格待补"
    if low is not None and high is not None and low != high:
        return f"¥{_compact_number(low)}-{_compact_number(high)}"
    value = low if low is not None else high
    return f"${_compact_number(value)}"



def _compact_number(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else f"{float(value):.2f}".rstrip("0").rstrip(".")
    return str(value)



def _route_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "asin": item.get("asin"),
        "title": item.get("title") or "未命名商品",
        "url": item.get("url"),
        "price_text": _route_item_price_text(item),
        "status": item.get("route_source_group") or item.get("status_label") or "待确认",
        "rationale": item.get("rationale") or item.get("detail_summary") or "",
    }



def _route_item_price_text(item: dict[str, Any]) -> str:
    low = _first_numeric(item.get("price_usd"), item.get("price"))
    high = _first_numeric(item.get("price_usd"), item.get("price"))
    return _route_price_text(low, high)



def _route_priority(route_id: Any) -> int:
    for definition in PRODUCT_ROUTE_DEFINITIONS:
        if definition["route_id"] == route_id:
            return int(definition["priority"])
    return 999



def _market_route_reference_items(candidate: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    tagged = candidate.get("market_structure", {}).get("tagged_products", [])
    if not isinstance(tagged, list):
        return []
    anchors = _market_anchor_terms(candidate)
    result: list[dict[str, Any]] = []
    for item in tagged:
        if not isinstance(item, dict):
            continue
        relevance = _competitor_market_relevance(item, anchors)
        if relevance["status"] == "剔除":
            continue
        result.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "route_source_group": "市场样本",
                "price_usd": item.get("price_usd") or item.get("price"),
                "asin": item.get("asin"),
                "market_boundary_status": relevance["status"],
                "rationale": "卖家精灵 Top 商品样本，用于路线级市场证据验证。"
                + (f" 边界状态：{relevance['status']}，{relevance['reason']}" if relevance["status"] != "相关" else ""),
            }
        )
        if len(result) >= limit:
            break
    return result



def _product_route_plain_summary(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return "产品路线还没拆开，下一步先按基础款、升级款、场景款、组合/套装和旁支观察分组。"
    parts = []
    for route in routes[:4]:
        name = str(route.get("route_name") or "未命名路线")
        count = _positive_count(route.get("candidate_count"))
        route_type = str(route.get("route_type") or "路线")
        if count:
            parts.append(f"{name}有 {count} 个候选，属于{route_type}，要单独补证据")
        elif route.get("always_consider"):
            parts.append(f"{name}暂时证据不足，但仍要主动补数，避免漏掉潜在路线")
    if not parts:
        parts.append("目前只有旁支或待确认候选，先补路线标签、关键词和代表竞品证据。")
    parts.append("不要只盯一个看起来最像的商品，先逐路线小深挖再决定主推。")
    return "；".join(parts)



def _build_route_deep_dive_plan(
    candidate: dict[str, Any],
    product_route_matrix: list[dict[str, Any]],
    voc_package: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not product_route_matrix:
        return []
    plan: list[dict[str, Any]] = []
    for route in product_route_matrix:
        if not isinstance(route, dict):
            continue
        item = _route_deep_dive_item(candidate, route, voc_package)
        if item:
            plan.append(item)
    plan.sort(key=lambda item: (int(item.get("sort_priority", 999)), str(item.get("route_name") or "")))
    return plan



def _route_deep_dive_item(
    candidate: dict[str, Any],
    route: dict[str, Any],
    voc_package: dict[str, Any] | None,
) -> dict[str, Any]:
    route_id = str(route.get("route_id") or "")
    route_type = str(route.get("route_type") or "路线")
    candidate_count = _positive_count(route.get("candidate_count"))
    priority_count = _positive_count(route.get("priority_count"))
    representative_items = route.get("representative_items") if isinstance(route.get("representative_items"), list) else []
    competitor_asins = _route_competitor_asins(candidate, route)
    review_summary = _route_review_evidence_summary(voc_package, route)
    recommended_depth = _route_recommended_depth(route_type, candidate_count, priority_count, competitor_asins)
    current_evidence_level = _route_current_evidence_level(candidate_count, priority_count, competitor_asins, review_summary)
    data_gap = _route_data_gaps(route_type, candidate_count, competitor_asins, review_summary)
    return {
        "route_id": route_id,
        "route_name": route.get("route_name"),
        "route_type": route_type,
        "recommended_depth": recommended_depth,
        "current_evidence_level": current_evidence_level,
        "why": _route_plan_why(route, recommended_depth, competitor_asins),
        "seller_sprite_exports": _route_list(route, "seller_sprite_exports"),
        "sorftime_checks": _route_list(route, "sorftime_checks"),
        "review_voc_asin_plan": competitor_asins,
        "review_coverage": review_summary,
        "route_search_terms": _route_list(route, "route_search_terms"),
        "decision_gate": _route_list(route, "decision_gate") or _default_route_decision_gate(route),
        "data_gaps": data_gap,
        "next_step": _route_next_step(recommended_depth, data_gap, route),
        "representative_market_items": representative_items[:3],
        "sort_priority": _route_plan_priority(route_type, recommended_depth, route_id),
    }



def _route_list(route: dict[str, Any], key: str) -> list[Any]:
    value = route.get(key)
    return list(value) if isinstance(value, list) else []



def _route_recommended_depth(
    route_type: str,
    candidate_count: int,
    priority_count: int,
    competitor_asins: list[dict[str, Any]],
) -> str:
    if route_type in {"主线", "升级", "场景", "组合"}:
        if candidate_count or competitor_asins:
            return "必须路线小深挖"
        return "必须主动补数"
    if route_type == "功能升级":
        return "小深挖观察" if candidate_count or competitor_asins else "作为规格维度验证"
    if route_type == "旁支":
        return "小深挖观察" if candidate_count or competitor_asins else "低优先补数"
    if priority_count:
        return "小深挖观察"
    return "观察，不进主推"



def _route_current_evidence_level(
    candidate_count: int,
    priority_count: int,
    competitor_asins: list[dict[str, Any]],
    review_summary: dict[str, Any],
) -> str:
    review_count = _positive_count(review_summary.get("matched_review_count"))
    if priority_count >= 3 and len(competitor_asins) >= 2 and review_count >= 20:
        return "强"
    if candidate_count or competitor_asins or review_count:
        return "中"
    return "弱"



def _route_data_gaps(
    route_type: str,
    candidate_count: int,
    competitor_asins: list[dict[str, Any]],
    review_summary: dict[str, Any],
) -> list[str]:
    gaps: list[str] = []
    if candidate_count <= 0:
        gaps.append("这条路线还没有明确市场样本，需要补代表 ASIN 或关键词结果。")
    if not competitor_asins:
        gaps.append("还缺这条路线的代表 ASIN，评价和 Sorftime 流量词无法单独判断。")
    matched_review_count = _positive_count(review_summary.get("matched_review_count"))
    matched_asins = review_summary.get("matched_asins") if isinstance(review_summary.get("matched_asins"), list) else []
    if matched_review_count < 30:
        gaps.append("评价样本还不够，至少补到 30 条以上再归纳痛点。")
    if route_type in {"主线", "升级", "场景", "组合"} and len(matched_asins) < 2:
        gaps.append("VOC 覆盖的 ASIN 太少，容易把单个竞品问题当成整条路线问题。")
    return gaps



def _route_plan_why(
    route: dict[str, Any],
    recommended_depth: str,
    competitor_asins: list[dict[str, Any]],
) -> str:
    route_name = str(route.get("route_name") or "这条路线")
    count = _positive_count(route.get("candidate_count"))
    price = str(route.get("price_text") or "价格待补")
    if "必须" in recommended_depth:
        return f"{route_name}不能混在大方向里看；现在有 {count} 个市场样本、价格 {price}，还要单独看竞品、评价和关键词入口。"
    if competitor_asins:
        return f"{route_name}已有可参考 ASIN，但还要确认它是主线机会还是旁支需求。"
    return f"{route_name}先保留观察，不要因为关键词相近就直接放进主推判断。"



def _route_next_step(recommended_depth: str, data_gaps: list[str], route: dict[str, Any]) -> str:
    if data_gaps:
        return data_gaps[0]
    if "规格维度" in recommended_depth:
        return "把这条路线的功能点写进基础款/升级款样品检查表。"
    if "必须" in recommended_depth:
        return "先补路线专属 ASIN、评价和关键词反查，再决定是否进完整深挖。"
    return str(route.get("decision_hint") or "先作为旁支观察，等证据变强再升级。")



def _route_plan_priority(route_type: str, recommended_depth: str, route_id: str) -> int:
    if "必须" in recommended_depth:
        return 10 + _route_priority(route_id)
    if route_type in {"场景", "组合"}:
        return 120 + _route_priority(route_id)
    if route_type == "功能升级":
        return 200 + _route_priority(route_id)
    if route_type == "旁支":
        return 300 + _route_priority(route_id)
    return 500 + _route_priority(route_id)



def _route_competitor_asins(candidate: dict[str, Any], route: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    route_id = str(route.get("route_id") or "")
    terms = _route_competitor_terms(route)
    groups = candidate.get("competitor_candidates", {})
    if not isinstance(groups, dict):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group_key, group_label in (
        ("top10", "标杆老品"),
        ("recent_winners", "近半年新品"),
        ("structure_supplement", "结构补充"),
    ):
        items = groups.get(group_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            if not _route_competitor_match(title, route_id, terms):
                continue
            asin = str(item.get("asin") or "").strip()
            if not asin or asin in seen:
                continue
            seen.add(asin)
            result.append(
                {
                    "asin": asin,
                    "title": title,
                    "competitor_type": group_label,
                    "price_usd": item.get("price"),
                    "monthly_units": item.get("monthly_units"),
                    "rating_count": item.get("rating_count"),
                    "reason": _route_competitor_reason(route, title),
                    "url": item.get("url"),
                }
            )
            if len(result) >= limit:
                return result
    return result



def _route_by_id(candidate: dict[str, Any], route_id: str) -> dict[str, Any]:
    profile = _route_profile(candidate, {})
    context = _build_product_context(candidate, {}, {}, profile)
    for definition in PRODUCT_ROUTE_DEFINITIONS:
        if definition.get("route_id") == route_id:
            return _route_definition_with_context(definition, context, profile, candidate)
    return {"route_id": route_id, "route_name": route_id}



def _route_competitor_terms(route: dict[str, Any]) -> tuple[str, ...]:
    terms = route.get("competitor_terms")
    if isinstance(terms, (list, tuple)):
        return tuple(str(term).lower() for term in terms if term)
    route_keywords = route.get("route_keywords")
    if isinstance(route_keywords, list):
        return tuple(str(term).lower() for term in route_keywords if term)
    return ()



def _route_competitor_match(title: str, route_id: str, terms: tuple[str, ...]) -> bool:
    text = title.lower()
    return bool(terms and any(term in text for term in terms))



def _route_competitor_reason(route: dict[str, Any], title: str) -> str:
    route_name = str(route.get("route_name") or "路线")
    return f"标题与「{route_name}」关键词匹配，适合单独进入路线级 VOC 或流量词验证：{title[:60]}"



def _route_review_evidence_summary(voc_package: dict[str, Any] | None, route: dict[str, Any]) -> dict[str, Any]:
    terms = tuple(str(term).lower() for term in route.get("review_terms", ()) if term)
    reviews = [item for item in (voc_package or {}).get("normalized_reviews", []) if isinstance(item, dict)]
    if not terms or not reviews:
        return {
            "matched_review_count": 0,
            "matched_asins": [],
            "note": "评价插件尚未覆盖这条路线，或还没有可匹配的评论文本。",
        }
    matched: list[dict[str, Any]] = []
    matched_asins: set[str] = set()
    for review in reviews:
        text = " ".join(
            str(review.get(key) or "").lower()
            for key in ("review_text", "review_text_zh", "variant", "color", "size")
        )
        if any(term in text for term in terms):
            matched.append(review)
            asin = str(review.get("asin") or "").strip()
            if asin:
                matched_asins.add(asin)
    sample_ids = [str(item.get("review_id") or "") for item in matched[:5] if item.get("review_id")]
    return {
        "matched_review_count": len(matched),
        "matched_asins": sorted(matched_asins),
        "sample_review_ids": sample_ids,
        "note": "仅按路线关键词粗筛评论，后续仍要由 Claude 结合原文判断真实痛点。",
    }



def _default_route_decision_gate(route: dict[str, Any]) -> list[str]:
    return [
        "这条路线有独立竞品、独立需求词和可追溯评论证据。",
        "评论痛点能转成明确产品规格或后续验证动作。",
        "该路线所在价格带有销量，并且不是被头部品牌完全锁死。",
    ]
