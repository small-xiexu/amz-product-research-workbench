#!/usr/bin/env python3
"""Report Generation Agent local serial fallback.

Reads report_data.seed.json, integrated_operator_judgment.json, and evidence
packets, then enhances the seed into report_data.json and generates an
operator-facing HTML report.

This module is for local development and regression tests. Formal delivery
requires Report Generation Agent-authored report_data.json and HTML; script
outputs must not be treated as final without the normal QA gate.

Architecture:
  report_data.seed.json
  + integrated_operator_judgment.json
  + evidence packets
  → enhance_seed_to_report_data()  → report_data.json
  → generate_operator_html()       → <品名>_分析报告.html
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.research_core.pipeline._utils import _report_value, as_list
from packages.research_core.pipeline.build_analysis_packet import _extract_product_name
from packages.research_core.pipeline.public_language import public_label, public_text


# ── CSS template ──────────────────────────────────────────────────────────

def _load_template_css() -> str:
    css_path = (
        Path(__file__).resolve().parents[3]
        / "skills"
        / "amazon-product-research"
        / "references"
        / "report_template.css"
    )
    return css_path.read_text(encoding="utf-8")


# ── Value helpers ─────────────────────────────────────────────────────────

def _rv(val: Any) -> str:
    """Extract display value from a value/source_path dict or plain value."""
    v = _report_value(val)
    return str(v).strip() if v is not None else ""


def _esc(text: str) -> str:
    """HTML-escape text content."""
    text = _public_html_text(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _public_html_text(text: str) -> str:
    """Remove backend data-source/tool names from operator-facing HTML."""
    replacements = {
        "卖家精灵": "第三方市场数据工具",
        "Sorftime": "第三方关键词数据工具",
        "market_research_statistics": "市场统计数据",
        "keyword_detail": "关键词明细数据",
        "product_traffic_terms": "商品流量词数据",
    }
    result = str(text)
    for raw, public in replacements.items():
        result = result.replace(raw, public)
    return public_text(result)


def _tag_html(label: str, level: str) -> str:
    """Render a <span class="tag ..."> element."""
    cls = _tag_class(level)
    return f'<span class="tag {cls}">{_esc(public_label(label))}</span>'


def _tag_class(level: str) -> str:
    """Return the CSS class for a semantic tag level."""
    color_map = {
        "strong": "tag-green",
        "watch": "tag-amber",
        "weak": "tag-red",
        "blocked": "tag-red",
        "高": "tag-red",
        "中": "tag-amber",
        "低": "tag-green",
        "go": "tag-green",
        "no_go": "tag-red",
        "P0": "tag-red",
        "P1": "tag-amber",
        "P2": "tag-green",
        "main_traffic": "tag-green",
        "conversion_quality": "tag-blue",
        "precise_long_tail": "tag-gray",
        "mixed_or_excluded": "tag-red",
        "must": "tag-red",
        "should": "tag-amber",
        "nice_to_have": "tag-green",
    }
    return color_map.get(str(level), "tag-gray")


def _bar_color(opportunity_level: str) -> str:
    return {
        "strong": "#059669",
        "watch": "#d97706",
        "weak": "#dc2626",
    }.get(opportunity_level, "#6b7280")


# ── Seed → Report Data Enhancement ───────────────────────────────────────

def _as_list(val: Any) -> list[Any]:
    """Return val as a list, or empty list if None/not-listable."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return []


def _is_filled(val: Any) -> bool:
    """Return True if val is a non-empty, non-placeholder judgment value."""
    if val is None:
        return False
    if isinstance(val, str) and val.strip() in ("", "__ai_judgment__"):
        return False
    if isinstance(val, (list, dict)) and len(val) == 0:
        return False
    return True


def enhance_seed_to_report_data(
    seed: dict[str, Any],
    judgment: dict[str, Any] | None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enhance report_data seed into formal report_data.json.

    Transcription priority:
    1. judgment deep-analysis fields (Lead Operator Agent output) — highest fidelity
    2. judgment decision-summary fields (verdict_reason, required_next_actions)
    3. template-fill fallback (mechanical, for serial_fallback mode)

    All source_paths are preserved. No new numbers are fabricated.
    """
    rd: dict[str, Any] = json.loads(json.dumps(seed, ensure_ascii=False))

    # ── provenance ─────────────────────────────────────────────────────
    rd["execution_provenance"] = {
        "agent_role": "Report Generation Agent",
        "execution_mode": "serial_fallback",
        "provenance_note": (
            "serial_fallback: judgment transcription + template fallback. "
            "Fields transcribed from integrated_operator_judgment deep-analysis "
            "when available; '__ai_judgment__' placeholders fall back to template text."
        ),
    }

    # ── Hero ────────────────────────────────────────────────────────────
    hero = rd.setdefault("hero", {})
    if judgment:
        jv = judgment.get("final_verdict", "")
        verdict_map = {
            "go": "建议进入小批量验证",
            "watch": "建议补齐数据后再评估",
            "no_go": "建议暂停推进",
            "blocked": "建议暂停推进",
        }
        hero["verdict"] = verdict_map.get(jv, hero.get("verdict", ""))
        hero["confidence"] = judgment.get("confidence", hero.get("confidence", ""))

        # Priority 1: route_recommendation.primary_recommendation (deep analysis)
        route_rec = judgment.get("route_recommendation") or {}
        primary = route_rec.get("primary_recommendation", "")
        if _is_filled(primary):
            hero["lead_analysis"] = public_text(primary)
        # Priority 2: verdict_reason (decision summary)
        elif _is_filled(judgment.get("verdict_reason", "")):
            hero["lead_analysis"] = public_text(judgment["verdict_reason"])
        elif not hero.get("lead_analysis"):
            hero["lead_analysis"] = "基于市场、竞争、价格、VOC、风险和数据质量六维评价的综合判断。"

    # ── Category Panorama ──────────────────────────────────────────────
    cp = rd.setdefault("category_panorama", {})
    insights = cp.get("insights")
    if isinstance(insights, list):
        for ins in insights:
            if isinstance(ins, dict):
                if not ins.get("title") or "待AI" in str(ins.get("title", "")):
                    ins["title"] = "类目市场信号"
                    ins["body"] = "基于 Top100 样本数据分析，具体数值见下表。"
                    ins["source_path"] = ins.get("source_path", "__ai_judgment__")

    # ── Route tradeoff ──────────────────────────────────────────────────
    tradeoffs = (judgment or {}).get("route_tradeoff") or []
    if tradeoffs and isinstance(tradeoffs, list):
        filled_tradeoffs = [
            {
                "route_name": t.get("route_name", ""),
                "gain": t.get("gain", ""),
                "lose": t.get("lose", ""),
                "best_for": t.get("best_for", ""),
                "worst_for": t.get("worst_for", ""),
            }
            for t in tradeoffs
            if isinstance(t, dict) and _is_filled(t.get("gain"))
        ]
        if filled_tradeoffs:
            rd["route_tradeoff"] = filled_tradeoffs

    # ── Competitor judgments ────────────────────────────────────────────
    competitors = _as_list(rd.get("competitors"))
    # Build weakness map lookup from judgment
    weakness_map: dict[str, dict[str, Any]] = {}
    if judgment:
        for w in _as_list(judgment.get("competitor_weakness_map") or []):
            if isinstance(w, dict) and w.get("asin"):
                weakness_map[str(w["asin"]).strip()] = w
    # Build benchmark lookup from judgment
    benchmark_map: dict[str, dict[str, Any]] = {}
    if judgment:
        for b in _as_list(judgment.get("competitor_benchmark") or []):
            if isinstance(b, dict) and b.get("asin"):
                benchmark_map[str(b["asin"]).strip()] = b

    for c in competitors:
        if not isinstance(c, dict):
            continue
        asin = _rv(c.get("asin", "")).strip()
        wm = weakness_map.get(asin, {})
        bm = benchmark_map.get(asin, {})

        # Transcribe weakness/counter from judgment
        if _is_filled(wm.get("fatal_weakness")):
            c["weakness"] = public_text(wm["fatal_weakness"])
        if _is_filled(wm.get("my_counter")):
            c["counter"] = public_text(wm["my_counter"])

        # Transcribe judgment from competitor_benchmark differentiation
        if _is_filled(bm.get("differentiation_direction")):
            c["judgment"] = public_text(bm["differentiation_direction"])
        elif not c.get("judgment"):
            # Template fallback
            role = _rv(c.get("asin_role", ""))
            price = _rv(c.get("price", ""))
            sales = _rv(c.get("monthly_sales", ""))
            if "primary" in str(role):
                c["judgment"] = f"核心参考竞品，月销 {sales}，定价 ${price}，作为类目基准。"
            elif "high_sales" in str(role):
                c["judgment"] = f"高销标杆，月销 {sales}，可参考其流量和转化策略。"
            elif "new_release" in str(role):
                c["judgment"] = f"新品样本，月销 {sales}，代表了近期进入者的竞争水平。"
            elif "premium" in str(role):
                c["judgment"] = f"高端锚点，定价 ${price}，代表了价格天花板。"
            else:
                c["judgment"] = f"参考竞品，月销 {sales}，作为竞争态势参考。"
    rd["competitors"] = competitors

    # ── Pain points ─────────────────────────────────────────────────────
    pain_points = _as_list(rd.get("pain_points"))
    voc_specs: dict[str, dict[str, Any]] = {}
    if judgment:
        for vs in _as_list(judgment.get("voc_to_spec") or []):
            if isinstance(vs, dict) and vs.get("dimension"):
                voc_specs[str(vs["dimension"]).strip()] = vs

    for pp in pain_points:
        if not isinstance(pp, dict):
            continue
        dim = _rv(pp.get("dimension", "")).strip()
        vs = voc_specs.get(dim, {})

        if _is_filled(vs.get("issue_description")):
            pp["issue_description"] = public_text(vs["issue_description"])
        elif not pp.get("issue_description"):
            pp["issue_description"] = f"竞品在{dim}方面存在用户反馈问题，需重点关注。"

        if _is_filled(vs.get("spec_requirement")):
            pp["spec_requirement"] = public_text(vs["spec_requirement"])
        elif not pp.get("spec_requirement"):
            pp["spec_requirement"] = "基于 VOC 分析制定品质标准，在打样阶段验证。"
    rd["pain_points"] = pain_points

    # ── Price band judgments ────────────────────────────────────────────
    price_bands = _as_list(rd.get("price_bands"))
    pb_analysis: dict[str, dict[str, Any]] = {}
    if judgment:
        for pb in _as_list(judgment.get("price_band_analysis") or []):
            if isinstance(pb, dict) and pb.get("range"):
                pb_analysis[str(pb["range"]).strip()] = pb

    for pb in price_bands:
        if not isinstance(pb, dict):
            continue
        band = _rv(pb.get("band", "")).strip()
        pba = pb_analysis.get(band, {})

        if _is_filled(pba.get("competitive_meaning")):
            pb["judgment"] = public_text(pba["competitive_meaning"])
        elif not pb.get("judgment"):
            level = _rv(pb.get("opportunity_level", ""))
            share = _rv(pb.get("unit_share", ""))
            if level == "strong":
                pb["judgment"] = f"${band} 段销量占比 {share}，机会信号强，建议作为主力定价段。"
            elif level == "watch":
                pb["judgment"] = f"${band} 段销量占比 {share}，需关注竞争密度，可选择性进入。"
            else:
                pb["judgment"] = f"${band} 段销量占比 {share}，竞争激烈或容量有限，谨慎进入。"
    rd["price_bands"] = price_bands

    # ── Keyword strategies ──────────────────────────────────────────────
    keywords = _as_list(rd.get("keywords"))
    kw_strategy: dict[str, str] = {}
    if judgment:
        ks = judgment.get("keyword_strategy") or {}
        for role_key in ("primary_attack", "testable", "negative"):
            for kw_entry in _as_list(ks.get(role_key) or []):
                if isinstance(kw_entry, dict):
                    kw_text = str(kw_entry.get("keyword", "")).strip()
                    rationale = kw_entry.get("strategy_rationale", "")
                    if kw_text and _is_filled(rationale):
                        kw_strategy[kw_text] = public_text(rationale)

    for kw in keywords:
        if not isinstance(kw, dict):
            continue
        kw_text = _rv(kw.get("keyword", "")).strip()
        if kw_text in kw_strategy:
            kw["strategy"] = kw_strategy[kw_text]
        elif not kw.get("strategy"):
            role = kw.get("role", "")
            cpc = _rv(kw.get("cpc", ""))
            if role == "main_traffic":
                kw["strategy"] = f"主攻词，CPC ${cpc}，作为 listing 核心流量词重点投放和埋词。"
            elif role == "conversion_quality":
                kw["strategy"] = f"转化词，CPC ${cpc}，长尾精准流量，投产比较高，建议精准投放。"
            elif role == "precise_long_tail":
                kw["strategy"] = f"长尾词，CPC ${cpc}，低竞争精准流量，适合前期低成本测款。"
            elif role == "mixed_or_excluded":
                kw["strategy"] = "混池或排除词，存在类目不匹配或流量不精准风险，建议否定或谨慎测试。"
            else:
                kw["strategy"] = f"关键词 {kw_text}，建议根据实际投放数据判断效果。"
    rd["keywords"] = keywords

    # ── Advantages ──────────────────────────────────────────────────────
    advantages = _as_list(rd.get("advantages"))
    for adv in advantages:
        if isinstance(adv, dict):
            if not adv.get("description") or "待AI" in str(adv.get("description", "")):
                adv["description"] = "基于市场数据和 VOC 分析识别到的品类切入点优势。"
                adv["severity"] = "中"
                adv["evidence_basis"] = "参考 evaluation_summary 各维度评分和证据包数据。"
            if not adv.get("mitigation") and not adv.get("evidence_basis"):
                adv["evidence_basis"] = "参考证据包分析。"
    rd["advantages"] = advantages

    # ── Risks ───────────────────────────────────────────────────────────
    risks = _as_list(rd.get("risks"))
    risk_mitigations: list[dict[str, Any]] = []
    if judgment:
        risk_mitigations = _as_list(judgment.get("risk_mitigation") or [])

    for i, risk in enumerate(risks):
        if not isinstance(risk, dict):
            continue
        rm = risk_mitigations[i] if i < len(risk_mitigations) else {}
        if isinstance(rm, dict):
            if _is_filled(rm.get("operational_meaning")):
                risk["description"] = public_text(rm["operational_meaning"])
            if _is_filled(rm.get("mitigation_path")):
                risk["mitigation"] = public_text(rm["mitigation_path"])
        if not risk.get("mitigation"):
            risk["mitigation"] = "在下一步中跟进验证，补齐缺失数据后再做判断。"
    rd["risks"] = risks

    # ── Next steps ──────────────────────────────────────────────────────
    if judgment:
        # Priority 1: validation_roadmap (deep analysis, phased plan)
        roadmap = _as_list(judgment.get("validation_roadmap") or [])
        if roadmap:
            new_steps = []
            for i, phase in enumerate(roadmap):
                if not isinstance(phase, dict):
                    continue
                title = phase.get("phase", "")
                actions = phase.get("actions") or []
                exit_criteria = phase.get("exit_criteria", "")
                if_fail = phase.get("if_fail", "")
                action_text = "；".join(str(a) for a in actions if a)
                desc = action_text
                if exit_criteria:
                    desc += f"【通过标准】{exit_criteria}"
                if if_fail:
                    desc += f"【不通过】{if_fail}"
                if title and action_text:
                    new_steps.append({
                        "order": i + 1,
                        "title": public_text(title),
                        "description": public_text(desc),
                        "source_path": f"integrated_operator_judgment.validation_roadmap[{i}]",
                    })
            if new_steps:
                rd["next_steps"] = new_steps

        # Priority 2: required_next_actions (decision summary, flat list)
        if not rd.get("next_steps"):
            j_actions = judgment.get("required_next_actions")
            if isinstance(j_actions, list) and j_actions:
                new_steps = []
                for i, action in enumerate(j_actions[:3]):
                    if isinstance(action, str) and action.strip():
                        new_steps.append({
                            "order": i + 1,
                            "title": public_text(action.strip()),
                            "description": "基于六维评价和集成判断的自动化建议。",
                            "source_path": f"integrated_operator_judgment.required_next_actions[{i}]",
                        })
                if new_steps:
                    rd["next_steps"] = new_steps

    # ── Go/No-Go conditions from judgment ───────────────────────────────
    if judgment:
        gonogo = rd.get("gonogo_conditions")
        if isinstance(gonogo, list):
            for i, gg in enumerate(gonogo):
                if isinstance(gg, dict):
                    gg["source_path"] = gg.get(
                        "source_path",
                        f"integrated_operator_judgment.operator_constraints[{i}]",
                    )
        if not gonogo and judgment.get("operator_constraints"):
            jv = judgment.get("final_verdict", "")
            rd["gonogo_conditions"] = [
                {
                    "condition": "六维评价无阻断项",
                    "go_threshold": "所有关键维度未出现阻断项",
                    "nogo_threshold": "任一核心维度当前不满足放行条件",
                    "current_status": "已通过" if jv != "blocked" else "未通过",
                    "source_path": "integrated_operator_judgment.final_verdict",
                },
                {
                    "condition": "数据质量可支撑结论",
                    "go_threshold": "数据质量可支撑判断，且没有用低置信证据支撑强结论",
                    "nogo_threshold": "数据质量当前不满足放行条件，或低置信证据支撑强结论",
                    "current_status": "待验证",
                    "source_path": "evaluation_summary.dimension_results.data_quality",
                },
                {
                    "condition": "上游阶段全部完成",
                    "go_threshold": "progress.json 所有阶段状态为 done",
                    "nogo_threshold": "存在未完成阶段",
                    "current_status": "待验证",
                    "source_path": "progress.json.stages",
                },
            ]

    # ── Data sources completeness ───────────────────────────────────────
    data_sources = rd.get("data_sources")
    if isinstance(data_sources, dict) and analysis:
        gaps = data_sources.get("data_gaps") or []
        if not gaps:
            analysis_gaps = analysis.get("blocking_gaps") or []
            if analysis_gaps:
                data_sources["data_gaps"] = [
                    {
                        "gap": g.get("gap", ""),
                        "impact": g.get("impact", ""),
                        "severity": g.get("severity", "warning"),
                    }
                    for g in analysis_gaps
                    if isinstance(g, dict)
                ]

    return rd


# ── HTML Section Builders ─────────────────────────────────────────────────

def _build_hero_html(hero: dict[str, Any], run_id: str) -> str:
    verdict = _rv(hero.get("verdict", ""))
    lead = _rv(hero.get("lead_analysis", ""))
    confidence = _rv(hero.get("confidence", ""))
    confidence_display = public_label(confidence, context="confidence") if confidence else ""
    metrics = hero.get("metrics") or {}

    metric_order = [
        ("target_market", "目标市场"),
        ("monthly_demand", "月销"),
        ("core_search_volume", "核心词月搜"),
        ("avg_price", "均价"),
        ("recommended_price", "关注价格带"),
        ("avg_rating", "类目均分"),
    ]

    metric_html_parts = []
    for key, label in metric_order:
        m = metrics.get(key, {})
        value = _rv(m.get("value", "")) if isinstance(m, dict) else str(m)
        metric_html_parts.append(
            f"""<div class="hero-metric">
      <div class="label">{_esc(label)}</div>
      <div class="value">{_esc(value)}</div>
    </div>"""
        )

    target = _rv(metrics.get("target_market", {}))
    product_name = target or run_id

    return f"""<section class="hero">
  <div class="eyebrow">选品调研 · {_esc(product_name)} · {_esc(confidence_display)}</div>
  <h1>{_esc(product_name)}</h1>
  <div class="verdict">{_esc(verdict)}</div>
  <p class="lead">{_esc(lead)}</p>
  <div class="hero-grid">
{chr(10).join(metric_html_parts)}
  </div>
</section>"""


def _build_category_html(cp: dict[str, Any]) -> str:
    categories = _as_list(cp.get("categories") or [])

    cat_rows = ""
    for cat in categories:
        if not isinstance(cat, dict):
            continue
        name = _rv(cat.get("category_name", ""))
        node = _rv(cat.get("node_id", ""))
        path = _rv(cat.get("category_path", ""))
        sales = _rv(cat.get("top100_monthly_sales", ""))
        revenue = _rv(cat.get("top100_monthly_revenue", ""))
        price = _rv(cat.get("avg_price", ""))
        role = _rv(cat.get("category_role", ""))
        reason = cat.get("reason", "")
        cat_rows += f"""<tr>
      <td class="tc">{_esc(name)}</td>
      <td class="keyword-cell">{_esc(node)}</td>
      <td class="tc">{_esc(path)}</td>
      <td class="tc">{_esc(sales)}</td>
      <td class="tc">{_esc(revenue)}</td>
      <td class="tc">{_esc(price)}</td>
      <td class="tc">{_tag_html(role, role)}</td>
      <td>{_esc(str(reason))}</td>
    </tr>"""

    insights = _as_list(cp.get("insights") or [])
    insight_cards = ""
    for ins in insights:
        if not isinstance(ins, dict):
            continue
        itype = ins.get("type", "good")
        title = ins.get("title", "")
        body = ins.get("body", "")
        insight_cards += f"""<div class="insight-card {_esc(str(itype))}">
      <h4>{_esc(str(title))}</h4>
      <p>{_esc(str(body))}</p>
    </div>"""

    if not insight_cards:
        insight_cards = (
            '<div class="insight-card good">'
            "<h4>市场信号</h4><p>基于 Top100 样本的数据分析结果如上表。</p></div>"
            '<div class="insight-card warn">'
            "<h4>关注点</h4><p>样本统计口径为 Top100 产品，不代表全部市场情况。</p></div>"
        )

    sub = cp.get("sub_market") or {}
    health = cp.get("market_health") or {}
    season = cp.get("seasonality") or {}

    sub_text = (
        f"子市场：{_esc(_rv(sub.get('product_form', '')))}，"
        f"预估月销 {_esc(_rv(sub.get('estimated_monthly_units', '')))}，"
        f"月销额 {_esc(_rv(sub.get('estimated_monthly_revenue', '')))}。"
    )
    health_text = (
        f"健康度：Top3品牌份额 {_esc(_rv(health.get('top3_brand_share', '')))}，"
        f"中国卖家份额 {_esc(_rv(health.get('china_seller_share', '')))}，"
        f"近3月新品份额 {_esc(_rv(health.get('new_3m_share', '')))}。"
        f"{_esc(_rv(health.get('concentration_note', '')))}"
    )
    peak = ", ".join(season.get("peak_months") or [])
    trough = ", ".join(season.get("trough_months") or [])
    ratio = _rv(season.get("peak_trough_ratio", ""))
    season_text = f"季节性：旺季 {_esc(peak)}，淡季 {_esc(trough)}，峰谷比 {_esc(ratio)}。"

    return f"""<section class="section">
  <h2>类目全景</h2>
  <p class="subtitle">样本边界：基于 Top100 产品数据，不代表整个类目。判断口径：先判断后数据。</p>
  <div class="table-scroll">
  <table style="width:1360px">
    <colgroup>
      <col style="width:180px">
      <col style="width:130px">
      <col style="width:250px">
      <col style="width:120px">
      <col style="width:130px">
      <col style="width:110px">
      <col style="width:120px">
      <col style="width:320px">
    </colgroup>
    <thead><tr>
      <th>类目名</th><th class="tc nowrap">Node ID</th><th>类目路径</th><th class="tc">月销(units)</th><th class="tc">月销额($)</th><th class="tc">均价($)</th><th class="tc">角色</th><th>判断理由</th>
    </tr></thead>
    <tbody>{cat_rows if cat_rows else '<tr><td colspan="8">暂无类目数据</td></tr>'}</tbody>
  </table>
  </div>
  <div class="insight-row">
{insight_cards}
  </div>
  <p class="subtitle">{sub_text} {health_text} {season_text}</p>
</section>"""


def _build_competitors_html(competitors: list[Any]) -> str:
    rows = ""
    for c in competitors:
        if not isinstance(c, dict):
            continue
        asin = _rv(c.get("asin", ""))
        route = _rv(c.get("route", ""))
        brand = _rv(c.get("brand", ""))
        price = _rv(c.get("price", ""))
        sales = _rv(c.get("monthly_sales", ""))
        rating = _rv(c.get("rating", ""))
        rcount = _rv(c.get("rating_count", ""))
        role = _rv(c.get("asin_role", ""))
        judgment = c.get("judgment", "")
        rows += f"""<tr>
      <td class="asin-cell">{_esc(asin)}</td>
      <td class="tc">{_esc(route)}</td>
      <td class="brand-cell"><div class="brand-stack"><strong>{_esc(brand)}</strong><span class="tag {_tag_class(role)}">{_esc(public_label(role))}</span></div></td>
      <td class="tc">{_esc(price)}</td>
      <td class="tc">{_esc(sales)}</td>
      <td class="tc">{_esc(rating)}</td>
      <td class="tc">{_esc(rcount)}</td>
      <td>{_esc(str(judgment))}</td>
    </tr>"""

    return f"""<section class="section">
  <h2>核心竞品</h2>
  <p class="subtitle">每条路线的代表竞品对比，帮助判断竞争态势。</p>
  <div class="table-scroll">
  <table style="width:1120px">
    <colgroup>
      <col style="width:130px">
      <col style="width:150px">
      <col style="width:170px">
      <col style="width:90px">
      <col style="width:90px">
      <col style="width:90px">
      <col style="width:100px">
      <col style="width:300px">
    </colgroup>
    <thead><tr>
      <th class="tc nowrap">ASIN</th><th class="tc">路线</th><th class="tc">品牌</th><th class="tc">价格($)</th><th class="tc">月销</th><th class="tc">评分</th><th class="tc">评论数</th><th>判断</th>
    </tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="8">暂无竞品数据</td></tr>'}</tbody>
  </table>
  </div>
</section>"""


def _build_pain_points_html(pain_points: list[Any]) -> str:
    rows = ""
    for pp in pain_points:
        if not isinstance(pp, dict):
            continue
        priority = pp.get("priority", "P1")
        dim = _rv(pp.get("dimension", ""))
        rcount = _rv(pp.get("review_count", ""))
        issue = pp.get("issue_description", "")
        spec = pp.get("spec_requirement", "")
        rows += f"""<tr>
      <td class="tc">{_tag_html(priority, priority)}</td>
      <td class="tc">{_esc(dim)}</td>
      <td class="tc">{_esc(rcount)}</td>
      <td>{_esc(str(issue))}</td>
      <td>{_esc(str(spec))}</td>
    </tr>"""

    return f"""<section class="section">
  <h2>用户痛点</h2>
  <p class="subtitle">基于差评提取核心痛点，直接指导产品打样和品质标准制定。</p>
  <div class="table-scroll">
  <table style="width:1240px">
    <colgroup>
      <col style="width:90px">
      <col style="width:160px">
      <col style="width:90px">
      <col style="width:450px">
      <col style="width:450px">
    </colgroup>
    <thead><tr>
      <th class="tc">优先级</th><th class="tc">痛点维度</th><th class="tc">提及数</th><th>竞品出了什么问题</th><th>你的产品应该做到</th>
    </tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="5">暂无痛点数据</td></tr>'}</tbody>
  </table>
  </div>
</section>"""


def _build_price_bands_html(price_bands: list[Any]) -> str:
    bars = ""
    for pb in price_bands:
        if not isinstance(pb, dict):
            continue
        band = _rv(pb.get("band", ""))
        share = _rv(pb.get("unit_share", ""))
        pcount = _rv(pb.get("product_count", ""))
        level = _rv(pb.get("opportunity_level", ""))
        height = _rv(pb.get("bar_height", "50"))
        judgment = pb.get("judgment", "")
        color = _bar_color(level)
        bars += f"""<div class="price-bar">
      <div class="bar" style="background:{color};height:{_esc(str(height))}px">{_esc(share)}</div>
      <div class="label">${_esc(band)}<br>{_esc(pcount)}个产品<br>{_esc(str(judgment))}</div>
    </div>"""

    return f"""<section class="section">
  <h2>价格带分布</h2>
  <p class="subtitle">各价格段的销量占比与竞争密度，帮助判断定价空间。</p>
  <div class="price-band">
{bars if bars else '<p>暂无价格带数据</p>'}
  </div>
</section>"""


def _build_keywords_html(keywords: list[Any]) -> str:
    rows = ""
    for kw in keywords:
        if not isinstance(kw, dict):
            continue
        role = kw.get("role", "")
        word = _rv(kw.get("keyword", ""))
        ms = _rv(kw.get("monthly_search_volume", ""))
        cpc = _rv(kw.get("cpc", ""))
        comp = _rv(kw.get("competitor_count", ""))
        strategy = kw.get("strategy", "")
        rows += f"""<tr>
      <td class="tc">{_tag_html(role, role)}</td>
      <td class="keyword-cell">{_esc(word)}</td>
      <td class="tc">{_esc(ms)}</td>
      <td class="tc">{_esc(cpc)}</td>
      <td class="tc">{_esc(comp)}</td>
      <td>{_esc(str(strategy))}</td>
    </tr>"""

    return f"""<section class="section">
  <h2>关键词与流量策略</h2>
  <p class="subtitle">按运营意图分层：主攻词 / 可测词 / 否定词，每条配策略说明。</p>
  <div class="table-scroll">
  <table style="width:1100px">
    <colgroup>
      <col style="width:90px">
      <col style="width:240px">
      <col style="width:100px">
      <col style="width:90px">
      <col style="width:100px">
      <col style="width:480px">
    </colgroup>
    <thead><tr>
      <th class="tc">角色</th><th>关键词</th><th class="tc">月搜索量</th><th class="tc">CPC($)</th><th class="tc">竞品数</th><th>策略说明</th>
    </tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="6">暂无关键词数据</td></tr>'}</tbody>
  </table>
  </div>
</section>"""


def _build_risks_next_html(
    risks: list[Any],
    advantages: list[Any],
    gonogo: list[Any],
    next_steps: list[Any],
) -> str:
    # Risk items
    risk_items = ""
    for r in risks:
        if not isinstance(r, dict):
            continue
        sev = r.get("severity", "中")
        desc = r.get("description", "")
        mitigation = r.get("mitigation", "")
        evidence = r.get("evidence_basis", "")
        note = mitigation or evidence
        risk_items += f"""<li>
      <span class="severity">{_tag_html(str(sev), str(sev))}</span>
      <div><strong>{_esc(str(desc))}</strong><br><small>{_esc(str(note))}</small></div>
    </li>"""

    # Advantage items
    adv_items = ""
    for a in advantages:
        if not isinstance(a, dict):
            continue
        desc = a.get("description", "")
        basis = a.get("evidence_basis", "")
        adv_items += f"""<li>
      <span class="severity">{_tag_html("优势", "strong")}</span>
      <div><strong>{_esc(str(desc))}</strong><br><small>{_esc(str(basis))}</small></div>
    </li>"""

    # Go/No-Go table
    gonogo_rows = ""
    for g in gonogo:
        if not isinstance(g, dict):
            continue
        cond = g.get("condition", "")
        go_t = g.get("go_threshold", "")
        nogo_t = g.get("nogo_threshold", "")
        status = g.get("current_status", "")
        gonogo_rows += f"""<tr>
      <td>{_esc(str(cond))}</td>
      <td>{_esc(str(go_t))}</td>
      <td>{_esc(str(nogo_t) or '—')}</td>
      <td class="tc">{_tag_html(str(status), str(status))}</td>
    </tr>"""

    # Next steps
    step_cards = ""
    for ns in next_steps if isinstance(next_steps, list) else []:
        if not isinstance(ns, dict):
            continue
        order = ns.get("order", "")
        title = ns.get("title", "")
        desc = ns.get("description", "")
        step_cards += f"""<div class="next-step">
      <div class="num">{_esc(str(order))}</div>
      <h4>{_esc(str(title))}</h4>
      <p>{_esc(str(desc))}</p>
    </div>"""

    if not step_cards:
        step_cards = (
            '<div class="next-step">'
            '<div class="num">1</div>'
            "<h4>补充数据</h4>"
            "<p>当前数据不足以形成强结论，建议补充关键数据后再评估。</p>"
            "</div>"
        )

    return f"""<section class="section">
  <h2>风险与下一步</h2>
  <p class="subtitle">风险与优势对照，放行条件表，下一步行动建议。</p>
  <div class="insight-row">
    <div class="insight-card warn">
      <h4>主要风险</h4>
      <ul class="risk-list">
{risk_items if risk_items else '<li>暂无已识别的风险</li>'}
      </ul>
    </div>
    <div class="insight-card good">
      <h4>核心优势</h4>
      <ul class="risk-list">
{adv_items if adv_items else '<li>数据驱动的优势需进一步分析</li>'}
      </ul>
    </div>
  </div>
  <h3 style="margin-top:16px">放行条件</h3>
  <div class="table-scroll">
  <table class="go-nogo" style="width:1180px">
    <colgroup>
      <col style="width:260px">
      <col style="width:350px">
      <col style="width:300px">
      <col style="width:270px">
    </colgroup>
    <thead><tr>
      <th>条件</th><th>放行条件</th><th>暂停条件</th><th class="tc">当前状态</th>
    </tr></thead>
    <tbody>{gonogo_rows if gonogo_rows else '<tr><td colspan="4">暂无放行条件</td></tr>'}</tbody>
  </table>
  </div>
  <h3 style="margin-top:16px">下一步</h3>
  <div class="next-steps">
{step_cards}
  </div>
</section>"""


# ── Main HTML Generator ──────────────────────────────────────────────────

def generate_operator_html(report_data: dict[str, Any]) -> str:
    """Generate operator-facing HTML report from report_data.json.

    Follows the Report Generation Agent specification exactly:
    - Inline report_template.css as <style> block
    - Only allowed class names from the agent spec
    - No internal terms (Agent, MCP, tool, packet, pipeline, spawn,
      evidence_packet, source_path) in output
    - Every number comes from report_data.json
    - Expert operator narrative style
    """
    css = _load_template_css()
    run_id = report_data.get("run_id", "")

    hero = report_data.get("hero") or {}
    cp = report_data.get("category_panorama") or {}
    competitors = _as_list(report_data.get("competitors"))
    pain_points = _as_list(report_data.get("pain_points"))
    price_bands = _as_list(report_data.get("price_bands"))
    keywords = _as_list(report_data.get("keywords"))
    risks = _as_list(report_data.get("risks"))
    advantages = _as_list(report_data.get("advantages"))
    gonogo = _as_list(report_data.get("gonogo_conditions"))
    next_steps = _as_list(report_data.get("next_steps"))

    sections = [
        _build_hero_html(hero, run_id),
        _build_category_html(cp),
        _build_competitors_html(competitors),
        _build_pain_points_html(pain_points),
        _build_price_bands_html(price_bands),
        _build_keywords_html(keywords),
        _build_risks_next_html(risks, advantages, gonogo, next_steps),
    ]

    body = "\n\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>选品分析报告</title>
<style>
{css}
</style>
</head>
<body>
<div class="page">
{body}
</div>
</body>
</html>
"""


# ── Validation ───────────────────────────────────────────────────────────

def validate_agent_output(
    report_data_path: Path, html_path: Path
) -> dict[str, Any]:
    """Validate Report Generation Agent output before script XLSX/QA phase.

    Checks:
    - report_data.json exists and is valid JSON
    - All 11 required sections present
    - No empty string source_path (blocker)
    - HTML exists and has all 6 required sections
    - HTML uses the exact report_template.css and only allowed template classes
    """
    issues: list[str] = []

    # Check report_data.json
    if not report_data_path.exists():
        return {"valid": False, "issues": ["report_data.json missing"]}

    rd = json.loads(report_data_path.read_text(encoding="utf-8"))

    from packages.research_core.pipeline.constants import (
        REQUIRED_REPORT_DATA_SECTIONS,
        REQUIRED_SECTION_MARKERS,
    )

    for section in REQUIRED_REPORT_DATA_SECTIONS:
        if section not in rd:
            issues.append(f"report_data.json missing section: {section}")

    # Check for empty source_path (blocker)
    empty_sp = _find_empty_source_paths(rd)
    if empty_sp:
        issues.append(
            f"report_data.json has {len(empty_sp)} empty source_path(s): "
            + ", ".join(empty_sp[:5])
        )

    # Check HTML
    if not html_path.exists():
        return {"valid": len(issues) == 0, "issues": issues + ["HTML missing"]}

    html = html_path.read_text(encoding="utf-8")

    for marker in REQUIRED_SECTION_MARKERS:
        if marker not in html:
            issues.append(f"HTML missing section: {marker}")

    from packages.research_core.pipeline.delivery_qa import (
        _has_inline_style,
        _has_no_fixed_data_source_section,
        _has_only_allowed_report_classes,
        _uses_report_template_css,
    )

    if not _has_inline_style(html_path):
        issues.append("HTML missing inline <style> block or uses external CSS")

    template_css = _uses_report_template_css(html_path)
    if not template_css["pass"]:
        issues.extend(template_css.get("hits", []))

    class_check = _has_only_allowed_report_classes(html_path)
    if not class_check["pass"]:
        issues.extend(class_check.get("hits", []))

    data_source_section = _has_no_fixed_data_source_section(html_path)
    if not data_source_section["pass"]:
        issues.extend(data_source_section.get("hits", []))

    return {"valid": len(issues) == 0, "issues": issues}


def _find_empty_source_paths(obj: Any, prefix: str = "") -> list[str]:
    """Find source_path fields that are empty strings (QA blocker)."""
    results: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if key == "source_path" and isinstance(val, str) and val == "":
                results.append(path)
            elif isinstance(val, (dict, list)):
                results.extend(_find_empty_source_paths(val, path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_find_empty_source_paths(item, f"{prefix}[{i}]"))
    return results


# ── Main Entry ───────────────────────────────────────────────────────────

def run_report_agent(
    run_dir: Path,
    *,
    judgment_path: Path | None = None,
    analysis_path: Path | None = None,
    seed_path: Path | None = None,
    report_data_path: Path | None = None,
    html_path: Path | None = None,
) -> dict[str, Any]:
    """Run Report Generation Agent for a run directory.

    Reads seed, judgment, and analysis_packet, then:
    1. Enhances seed → report_data.json
    2. Generates operator-facing HTML

    Returns execution provenance dict for audit trail.
    """
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    _seed = seed_path or (analysis_dir / "report_data.seed.json")
    _judgment = judgment_path or (analysis_dir / "integrated_operator_judgment.json")
    _analysis = analysis_path or (analysis_dir / "analysis_packet.json")
    _rd = report_data_path or (analysis_dir / "report_data.json")

    # Load seed (required)
    if not _seed.exists():
        return {
            "status": "error",
            "error": f"Seed not found: {_seed}",
            "provenance": "serial_fallback",
        }
    seed = json.loads(_seed.read_text(encoding="utf-8"))

    # Load judgment (optional)
    judgment = None
    if _judgment.exists():
        judgment = json.loads(_judgment.read_text(encoding="utf-8"))

    # Load analysis_packet (optional, for data enhancement)
    analysis = None
    if _analysis and _analysis.exists():
        analysis = json.loads(_analysis.read_text(encoding="utf-8"))

    # Determine product name for HTML filename. Keep this aligned with the
    # post-Agent XLSX/QA step, which looks for <product>_分析报告.html.
    product_name = _extract_product_name(run_dir)
    if _html := (html_path):
        pass
    else:
        _html = analysis_dir / f"{product_name}_分析报告.html"

    # Step 1: Enhance seed → report_data.json
    report_data = enhance_seed_to_report_data(seed, judgment, analysis)
    _rd.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Step 2: Generate HTML
    html = generate_operator_html(report_data)
    _html.write_text(html, encoding="utf-8")

    # Validate output
    validation = validate_agent_output(_rd, _html)

    return {
        "status": "ok" if validation["valid"] else "warning",
        "provenance": "serial_fallback",
        "agent_role": "Report Generation Agent",
        "execution_mode": "serial_fallback",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outputs": {
            "report_data": str(_rd),
            "html": str(_html),
        },
        "validation": validation,
    }
