#!/usr/bin/env python3
"""Build a zero-to-one research plan from a fuzzy selection brief."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def compact_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(compact_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {compact_text(item)}" for key, item in value.items())
    return str(value).strip()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "product-research"


def build_branches(brief: dict[str, Any]) -> list[dict[str, Any]]:
    scope = brief.get("search_scope", {}) if isinstance(brief.get("search_scope"), dict) else {}
    keywords = [str(k).strip() for k in scope.get("keywords", []) if str(k).strip()]
    categories = [str(c).strip() for c in scope.get("categories", []) if str(c).strip()]
    scenarios = [str(s).strip() for s in scope.get("scenarios", []) if str(s).strip()]
    exclusions = [str(r).strip() for r in brief.get("exclusion_rules", []) if str(r).strip()]
    hypotheses = [str(h).strip() for h in brief.get("operator_hypotheses", []) if str(h).strip()]

    if keywords:
        branches = []
        for idx, kw in enumerate(keywords[:3]):
            other_kws = [k for k in keywords if k != kw]
            positioning = hypotheses[idx] if idx < len(hypotheses) else (
                f"基于关键词「{kw}」探索市场，先看大盘体量、价格带、集中度和近半年新品机会。"
            )
            branches.append({
                "name": f"{kw} 方向",
                "positioning": positioning,
                "primary_keywords": [kw] + other_kws[:2],
                "backup_keyword": scenarios[0] if scenarios else (other_kws[0] if other_kws else kw),
                "mix_risks": other_kws + ([s for s in scenarios if s not in other_kws])[:2],
                "initial_exclusions": exclusions,
                "why_mainline": (
                    "运营指定的主线关键词；先用此词跑第一轮市场数据，再由真实结果决定是否拆细分。"
                    if idx == 0 else
                    "运营补充的次要方向；可作旁支参考，待主线数据回来后再决定是否单独深挖。"
                ),
            })
        return branches

    if scenarios:
        return [
            {
                "name": f"{s} 场景方向",
                "positioning": f"从「{s}」应用场景切入，先找场景主词再看市场大盘。",
                "primary_keywords": [s],
                "backup_keyword": categories[0] if categories else s,
                "mix_risks": [x for x in scenarios if x != s],
                "initial_exclusions": exclusions,
                "why_mainline": "从使用场景切入，具体关键词待第一轮数据后收敛。",
            }
            for s in scenarios[:3]
        ]

    base = categories[0] if categories else str(scope.get("free_text") or "product idea")
    return [
        {
            "name": f"{base} 方向预审",
            "positioning": "当前方向较模糊，先做市场大盘和搜索结果预审，由真实数据反推细分方向。",
            "primary_keywords": [base],
            "backup_keyword": base,
            "mix_risks": ["相邻场景", "同词不同品", "低价配件"],
            "initial_exclusions": exclusions,
            "why_mainline": "当前输入不足以拆出稳定细分，先用最贴近的主词跑第一轮数据，再由真实数据反推分支。",
        }
    ]


def build_export_guide(branch: dict[str, Any], site: str) -> list[dict[str, Any]]:
    primary_keywords = branch.get("primary_keywords", [])[:3]
    backup_keyword = branch.get("backup_keyword")
    return [
        {
            "step": "第一轮市场/搜索导出",
            "tool": "卖家精灵：选市场 / 市场分析 + 查竞品 / 搜索结果 Top100",
            "input": "；".join(primary_keywords),
            "output": "每个主关键词各导出市场分析和搜索结果/Top100。文件放入同一个导出文件夹。",
            "why": "先看大盘、价格带、销量、集中度、新品比例和混池程度，不直接拍板。",
        },
        {
            "step": "第一轮增强导出",
            "tool": "卖家精灵：ABA 数据选品",
            "input": "；".join(primary_keywords + ([backup_keyword] if backup_keyword else [])),
            "output": "查询最近完整月份，导出关键词搜索量、排名、PPC、点击/转化相关字段。",
            "why": "用 ABA 校验真实搜索需求和点击/转化集中度，避免只看搜索结果误判。",
        },
        {
            "step": "关键词反查",
            "tool": "卖家精灵：关键词反查",
            "input": "先待补。系统读取搜索结果后，会推荐 3-8 个 ASIN 给用户复制。",
            "output": "导出反查关键词表，补充流量词、自然排名、广告排名和前十 ASIN。",
            "why": "反查对象必须来自真实候选池，不能在没有 Top100 明细时靠猜。",
        },
        {
            "step": "保存规则",
            "tool": "本地文件夹",
            "input": f"卖家精灵导出_{{品类名}}_{{YYYYMMDD}}，站点 {site}",
            "output": "把所有 Excel/CSV 放到同一个文件夹，PDF 只作视觉参考。",
            "why": "系统会先做数据盘点和缺失检查，再进入候选池预审。",
        },
    ]


def build_plan(brief: dict[str, Any], task_name: str | None = None) -> dict[str, Any]:
    branches = build_branches(brief)
    main_branch = branches[0]
    site = brief.get("site") or "US"
    generated_at = datetime.now(timezone.utc).isoformat()
    name = task_name or brief.get("brief_id") or main_branch.get("name")
    return {
        "metadata": {
            "plan_id": "zero-to-one-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "task_name": name,
            "site": site,
            "generated_at": generated_at,
            "mode": "manual_export_first",
        },
        "source_brief": brief,
        "initial_hypothesis_card": {
            "recommended_mainline": main_branch.get("name"),
            "recommendation_reason": main_branch.get("why_mainline"),
            "candidate_branches": branches,
            "decision_rule": "运营可以选择主线、改主线或补充禁区；如果不调整，就按推荐主线进入第一轮卖家精灵导出。",
        },
        "seed_keywords": {
            "primary_keywords": main_branch.get("primary_keywords", [])[:3],
            "backup_keyword": main_branch.get("backup_keyword"),
            "negative_or_mixed_keywords": main_branch.get("mix_risks", []),
            "notes": "第一轮只给少量精准主词，避免卖家精灵导出过宽导致混池；大词和旁支词只用于识别混池，不直接全部导出。",
        },
        "seller_sprite_export_guide": build_export_guide(main_branch, str(site)),
        "human_gate": {
            "checkpoint": "第一轮导出前确认",
            "questions": [
                "推荐主线是否符合当前想看的产品形态？",
                "哪些旁支场景要保留参考，哪些要直接排除？",
                "第一轮是否只按这 2-3 个主关键词导出？",
            ],
            "default_if_no_change": "按推荐主线和主关键词继续。",
        },
        "data_rules": [
            "没有真实导出数据时，只能输出导出指引，不能形成选品结论。",
            "导入文件后先做数据盘点和缺失项检查，再生成候选池预审。",
            "候选名称、类目、关键词和市场数据明显不一致时暂停确认。",
            "预审阶段只决定是否值得深挖，利润、合规、知产和评论 VOC 不直接脑补。",
        ],
        "next_action": "请先确认初始候选假设卡，再按导出引导准备卖家精灵数据。",
    }


def render_markdown(plan: dict[str, Any]) -> str:
    metadata = plan.get("metadata", {})
    hypothesis = plan.get("initial_hypothesis_card", {})
    seed = plan.get("seed_keywords", {})
    lines = [
        "# 从 0 到 1 选品调研计划",
        "",
        f"- 任务：{metadata.get('task_name', '待填')}",
        f"- 站点：{metadata.get('site', 'US')}",
        f"- 生成时间：{metadata.get('generated_at', '待填')}",
        "",
        "## 初始候选假设卡",
        "",
        f"- 推荐主线：{hypothesis.get('recommended_mainline', '待填')}",
        f"- 推荐理由：{hypothesis.get('recommendation_reason', '待填')}",
        f"- 决策规则：{hypothesis.get('decision_rule', '待填')}",
        "",
        "### 可选分支",
        "",
    ]
    for index, branch in enumerate(hypothesis.get("candidate_branches", []), start=1):
        lines.extend(
            [
                f"{index}. {branch.get('name', '未命名分支')}",
                f"   - 定位：{branch.get('positioning', '待填')}",
                f"   - 主关键词：{', '.join(branch.get('primary_keywords', []))}",
                f"   - 备选词：{branch.get('backup_keyword', '待填')}",
                f"   - 混池风险：{', '.join(branch.get('mix_risks', []))}",
                f"   - 初始排除：{', '.join(branch.get('initial_exclusions', []))}",
            ]
        )
    lines.extend(
        [
            "",
            "## 第一轮关键词",
            "",
            f"- 主关键词：{', '.join(seed.get('primary_keywords', []))}",
            f"- 备选词：{seed.get('backup_keyword', '待填')}",
            f"- 混池/负向词：{', '.join(seed.get('negative_or_mixed_keywords', []))}",
            f"- 说明：{seed.get('notes', '')}",
            "",
            "## 卖家精灵导出引导",
            "",
        ]
    )
    for item in plan.get("seller_sprite_export_guide", []):
        lines.extend(
            [
                f"### {item.get('step', '步骤')}",
                f"- 工具：{item.get('tool', '待填')}",
                f"- 输入：{item.get('input', '待填')}",
                f"- 输出：{item.get('output', '待填')}",
                f"- 目的：{item.get('why', '待填')}",
                "",
            ]
        )
    lines.extend(
        [
            "## 人工确认点",
            "",
            *[f"- {question}" for question in plan.get("human_gate", {}).get("questions", [])],
            f"- 默认处理：{plan.get('human_gate', {}).get('default_if_no_change', '待填')}",
            "",
            "## 数据原则",
            "",
            *[f"- {item}" for item in plan.get("data_rules", [])],
            "",
            f"下一步：{plan.get('next_action', '待填')}",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a zero-to-one research plan from selection_brief JSON.")
    parser.add_argument("selection_brief", help="Path to selection_brief JSON.")
    parser.add_argument("output_dir", help="Directory to write zero_to_one_plan.json/md.")
    parser.add_argument("--task-name", default=None, help="Optional task display name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    brief_path = Path(args.selection_brief).expanduser().resolve()
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    plan = build_plan(brief, task_name=args.task_name)
    out = Path(args.output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "zero_to_one_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "zero_to_one_plan.md").write_text(render_markdown(plan), encoding="utf-8")
    print(f"Wrote zero-to-one plan: {out}")


if __name__ == "__main__":
    main()
