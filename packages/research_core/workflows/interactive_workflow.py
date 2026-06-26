"""Interactive workflow state and next-action planning.

This module models the AI + operator flow. It does not fetch data or render
reports; it tells the assistant when to call tools, when to ask the operator,
and what evidence is available for the final report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


WorkflowMode = Literal["broad_discovery", "targeted_deep_dive"]
WorkflowStage = Literal[
    "intent_intake",
    "exploration_planning",
    "seller_sprite_request",
    "data_inventory",
    "candidate_pool_review",
    "boundary_confirmation",
    "voc_batch_planning",
    "voc_analysis",
    "deep_dive",
    "final_decision",
]
ActionType = Literal[
    "operator_decision",
    "operator_export",
    "operator_upload",
    "mcp_call",
    "local_script",
    "review_crawl",
    "render_report",
    "wait",
]


STAGE_ORDER: list[WorkflowStage] = [
    "intent_intake",
    "exploration_planning",
    "seller_sprite_request",
    "data_inventory",
    "candidate_pool_review",
    "boundary_confirmation",
    "voc_batch_planning",
    "voc_analysis",
    "deep_dive",
    "final_decision",
]


@dataclass(frozen=True)
class EvidenceRef:
    ref_type: str
    ref_id: str
    path: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_type": self.ref_type,
            "ref_id": self.ref_id,
            "path": self.path,
            "note": self.note,
        }


@dataclass(frozen=True)
class NextActionOption:
    id: str
    label: str
    impact: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "impact": self.impact,
        }


@dataclass(frozen=True)
class RecommendedAction:
    action_type: ActionType
    label: str
    reason: str
    mcp_tools: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": self.action_type,
            "label": self.label,
            "reason": self.reason,
        }
        if self.mcp_tools:
            d["mcp_tools"] = self.mcp_tools
        return d


@dataclass(frozen=True)
class NextActionCard:
    stage: WorkflowStage
    decision_required: bool
    question: str
    recommended_action: RecommendedAction
    options: list[NextActionOption] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "decision_required": self.decision_required,
            "question": self.question,
            "recommended_action": self.recommended_action.to_dict(),
            "options": [item.to_dict() for item in self.options],
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
        }


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    stage: WorkflowStage
    actor: str
    decision: str
    rationale: str
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "stage": self.stage,
            "actor": self.actor,
            "decision": self.decision,
            "rationale": self.rationale,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "created_at": self.created_at or utc_now(),
        }


@dataclass(frozen=True)
class WorkflowState:
    workflow_id: str
    mode: WorkflowMode
    stage: WorkflowStage
    initial_intent: str
    site: str = "US"
    known_inputs: dict[str, Any] = field(default_factory=dict)
    missing_inputs: list[str] = field(default_factory=list)
    decision_required: bool = False
    operator_question: str = ""
    next_actions: list[NextActionCard] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    decision_log: list[DecisionRecord] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "mode": self.mode,
            "stage": self.stage,
            "initial_intent": self.initial_intent,
            "site": self.site,
            "known_inputs": self.known_inputs,
            "missing_inputs": self.missing_inputs,
            "decision_required": self.decision_required,
            "operator_question": self.operator_question,
            "next_actions": [item.to_dict() for item in self.next_actions],
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "decision_log": [item.to_dict() for item in self.decision_log],
            "updated_at": self.updated_at or utc_now(),
        }


def create_initial_state(
    workflow_id: str,
    mode: WorkflowMode,
    initial_intent: str,
    site: str = "US",
) -> WorkflowState:
    state = WorkflowState(
        workflow_id=workflow_id,
        mode=mode,
        stage="intent_intake",
        initial_intent=initial_intent,
        site=site,
        missing_inputs=_initial_missing_inputs(mode),
    )
    return plan_next_action(state)


def plan_next_action(state: WorkflowState) -> WorkflowState:
    card = build_next_action_card(state)
    return WorkflowState(
        workflow_id=state.workflow_id,
        mode=state.mode,
        stage=state.stage,
        initial_intent=state.initial_intent,
        site=state.site,
        known_inputs=state.known_inputs,
        missing_inputs=state.missing_inputs,
        decision_required=card.decision_required,
        operator_question=card.question,
        next_actions=[card],
        evidence_refs=state.evidence_refs,
        decision_log=state.decision_log,
        updated_at=utc_now(),
    )


def build_next_action_card(state: WorkflowState) -> NextActionCard:
    if state.stage == "intent_intake":
        return _intent_intake_card(state)
    if state.stage == "exploration_planning":
        return _exploration_planning_card(state)
    if state.stage == "seller_sprite_request":
        return _seller_sprite_request_card(state)
    if state.stage == "data_inventory":
        return _data_inventory_card(state)
    if state.stage == "candidate_pool_review":
        return _candidate_pool_review_card(state)
    if state.stage == "boundary_confirmation":
        return _boundary_confirmation_card(state)
    if state.stage == "voc_batch_planning":
        return _voc_batch_planning_card(state)
    if state.stage == "voc_analysis":
        return _voc_analysis_card(state)
    if state.stage == "deep_dive":
        return _deep_dive_card(state)
    return _final_decision_card(state)


def advance_stage(state: WorkflowState, decision: DecisionRecord | None = None) -> WorkflowState:
    next_stage = _next_stage(state.stage)
    decision_log = list(state.decision_log)
    if decision:
        decision_log.append(decision)
    advanced = WorkflowState(
        workflow_id=state.workflow_id,
        mode=state.mode,
        stage=next_stage,
        initial_intent=state.initial_intent,
        site=state.site,
        known_inputs=state.known_inputs,
        missing_inputs=_missing_inputs_for_stage(next_stage, state.mode, state.known_inputs),
        evidence_refs=state.evidence_refs,
        decision_log=decision_log,
        updated_at=utc_now(),
    )
    return plan_next_action(advanced)


def workflow_state_from_dict(data: dict[str, Any]) -> WorkflowState:
    evidence_refs = [EvidenceRef(**item) for item in data.get("evidence_refs", [])]
    decision_log = [
        DecisionRecord(
            decision_id=item.get("decision_id", ""),
            stage=item.get("stage", "intent_intake"),
            actor=item.get("actor", ""),
            decision=item.get("decision", ""),
            rationale=item.get("rationale", ""),
            evidence_refs=[EvidenceRef(**ref) for ref in item.get("evidence_refs", [])],
            created_at=item.get("created_at", ""),
        )
        for item in data.get("decision_log", [])
    ]
    return WorkflowState(
        workflow_id=str(data.get("workflow_id", "")),
        mode=data.get("mode", "targeted_deep_dive"),
        stage=data.get("stage", "intent_intake"),
        initial_intent=str(data.get("initial_intent", "")),
        site=str(data.get("site", "US")),
        known_inputs=dict(data.get("known_inputs", {})),
        missing_inputs=list(data.get("missing_inputs", [])),
        decision_required=bool(data.get("decision_required", False)),
        operator_question=str(data.get("operator_question", "")),
        next_actions=[],
        evidence_refs=evidence_refs,
        decision_log=decision_log,
        updated_at=str(data.get("updated_at", "")),
    )


def _intent_intake_card(state: WorkflowState) -> NextActionCard:
    if state.mode == "broad_discovery":
        return NextActionCard(
            stage=state.stage,
            decision_required=True,
            question="请先说清这次想解决什么场景/痛点，再确认目标站点、禁做类目、价格/重量偏好。",
            recommended_action=RecommendedAction(
                "operator_decision",
                "确认需求边界",
                "先从场景和痛点入手，避免一上来就把系统带进工厂或店铺思路里。",
            ),
            options=[
                NextActionOption("confirm_boundary", "确认场景边界", "进入方向拆解和类目探索。"),
                NextActionOption("add_constraints", "补充限制", "先补禁区、价格带和数据偏好。"),
            ],
        )
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请先说清你关心的场景/痛点，再确认指定方向的产品边界：包含哪些形态，排除哪些混池场景？",
        recommended_action=RecommendedAction(
            "operator_decision",
            "确认场景边界",
            "指定方向深挖前先把场景说清，避免关键词一响就把工厂/店铺货表当成答案。",
        ),
        options=[
            NextActionOption("confirm_product_boundary", "确认边界", "进入关键词/导出规划。"),
            NextActionOption("refine_product_boundary", "修正边界", "补充保留、排除、可参考场景和痛点。"),
        ],
    )


def _exploration_planning_card(state: WorkflowState) -> NextActionCard:
    if state.mode == "broad_discovery":
        return NextActionCard(
            stage=state.stage,
            decision_required=False,
            question="下一步先用 MCP 做宽类目探索，还是让运营导出卖家精灵选市场数据？",
            recommended_action=RecommendedAction(
                "mcp_call",
                "调用 Sorftime 宽类目初探",
                "当前还没有可落地导出关键词，先用低成本类目探索拆 2-4 个方向，与卖家精灵导出并行。",
                mcp_tools=[
                    {
                        "tool": "search_categories_broadly",
                        "purpose": "完全无方向时找细分类目入口",
                        "params_hint": "keyword: 根据运营意图填写品类描述（英文）",
                        "credits": 1,
                    },
                    {
                        "tool": "category_report",
                        "purpose": "拉取 2-3 个候选方向的实时 Top100，快速看月销量、价格、集中度和新品占比",
                        "params_hint": "nodeId: 从 search_categories_broadly 返回结果获取",
                        "credits": 1,
                        "repeat": "每个候选方向各调一次",
                    },
                    {
                        "tool": "keyword_list",
                        "purpose": "获取推荐主方向的核心词搜索量量级",
                        "params_hint": "keyword: 品类英文名",
                        "credits": 1,
                    },
                ],
            ),
            options=[
                NextActionOption("call_sorftime_broad", "先调 MCP 扫方向", "快速拆方向，避免盲导出。"),
                NextActionOption("request_market_export", "直接导出选市场 200 条", "适合运营已有明确类目入口。"),
            ],
        )
    return NextActionCard(
        stage=state.stage,
        decision_required=False,
        question="下一步先用 Sorftime 快验指定方向，再决定是否生成卖家精灵导出清单。",
        recommended_action=RecommendedAction(
            "mcp_call",
            "Sorftime 前置快验",
            "指定方向深挖模式：卖家精灵导出前先用 4-6 积分验证方向是否值得继续，通过后给定向导出清单。",
            mcp_tools=[
                {
                    "tool": "category_search_from_product_name",
                    "purpose": "从产品名定位 Amazon 类目节点",
                    "params_hint": "product_name: 运营给出的方向名称（英文）",
                    "credits": 1,
                },
                {
                    "tool": "category_report",
                    "purpose": "拉取实时 Top100，判断销量体量、价格带、集中度、新品机会",
                    "params_hint": "nodeId: 从 category_search_from_product_name 返回结果获取",
                    "credits": 1,
                },
                {
                    "tool": "keyword_detail",
                    "purpose": "获取 2-3 个主词的搜索量 + CPC + 首页竞品数量",
                    "params_hint": "keyword: 品类核心英文词（2-3 个，不给大词包）",
                    "credits": 1,
                    "repeat": "每个关键词各调一次",
                },
            ],
        ),
        options=[
            NextActionOption("call_sorftime_quick_verify", "先调 MCP 快验", "若结论为放弃，直接止损不用导出。"),
            NextActionOption("request_seller_sprite", "直接生成导出清单", "运营已有把握时跳过快验。"),
        ],
    )


def _seller_sprite_request_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请按 AI 给出的关键词/类目清单导出卖家精灵数据，并上传导出文件夹。",
        recommended_action=RecommendedAction(
            "operator_export",
            "导出并上传卖家精灵数据",
            "缺少 Top100/市场分析时不能进入正式候选池和深挖。",
        ),
        options=[
            NextActionOption("upload_exports", "已上传导出文件", "进入数据盘点。"),
            NextActionOption("need_export_help", "需要导出说明", "AI 输出具体页面、关键词和文件要求。"),
        ],
    )


def _data_inventory_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=False,
        question="下一步读取导出文件，检查缺失项、有效行列和混池风险。",
        recommended_action=RecommendedAction(
            "local_script",
            "运行导入盘点",
            "先确认数据是否足够，不直接生成正式报告。",
        ),
        options=[
            NextActionOption("inspect_exports", "盘点导出文件", "生成 import_manifest 和缺失项。"),
            NextActionOption("request_more_data", "补导出", "数据缺失时暂停正式流程。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _candidate_pool_review_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请先看候选池和产品路线矩阵：基础款、升级款、场景款、组合/套装款、功能/材质升级、小众形态分别保留还是排除？",
        recommended_action=RecommendedAction(
            "operator_decision",
            "确认候选池和路线矩阵",
            "先确认路线，再决定深挖候选；避免只选一个看起来最像的款式，漏掉升级款或场景款。",
        ),
        options=[
            NextActionOption("confirm_route_matrix", "确认路线矩阵", "进入路线边界确认和路线级补数计划。"),
            NextActionOption("rename_routes", "改路线名称", "当路线名还是目标产品/标准配置这类泛称时，先按真实产品形态重命名。"),
            NextActionOption("merge_sparse_routes", "合并空路线", "把没有候选、没有 ASIN、没有关键词证据的路线合并或隐藏。"),
            NextActionOption("adjust_route_labels", "调整路线分类", "修正基础/升级/场景/组合/小众形态后重新生成候选池。"),
            NextActionOption("exclude_mixed_pool", "排除混池项", "更新排除词、形态禁区或场景边界后重跑。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _boundary_confirmation_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请确认每条保留路线的角色：哪条做主推基准，哪条做升级验证，哪条只是场景/组合/小众形态观察？",
        recommended_action=RecommendedAction(
            "operator_decision",
            "确认路线边界",
            "边界确认后先做路线级小深挖：每条保留路线都要有关键词、竞品 ASIN、类目 Top100 和 VOC 批次。",
        ),
        options=[
            NextActionOption("confirm_route_roles", "确认路线角色", "为每条保留路线生成补数计划。"),
            NextActionOption("rename_route_by_shape", "按形态改名", "把泛化路线名改成运营能理解的款式名、场景名或规格名。"),
            NextActionOption("promote_route", "提升某条路线", "把场景/组合/升级路线提升为重点验证。"),
            NextActionOption("demote_route", "降级某条路线", "把证据弱或混池路线降为观察/排除。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _voc_batch_planning_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请确认每条保留路线的 VOC ASIN 批次：标准款、升级、场景、组合和小众形态要分开抓评论，不能混成一个结论。",
        recommended_action=RecommendedAction(
            "mcp_call",
            "路线补数 + 确认 VOC ASIN 批次",
            "路线矩阵确认后，每条保留路线都要补代表 ASIN、主词、Sorftime 流量词和小类 Top100，再决定哪 1-2 条进完整深挖。",
            mcp_tools=[
                {
                    "tool": "potential_product",
                    "purpose": "按路线找潜力新品和周边竞品，补齐路线专属 ASIN",
                    "params_hint": "searchName: 本路线英文关键词；amzSite: 'US'（仅支持 US/GB/DE）",
                    "credits": 1,
                    "timing": "路线矩阵确认后，优先给证据不足但值得看的路线调用",
                },
            ],
        ),
        options=[
            NextActionOption("call_route_extend", "先补路线 ASIN", "用 potential_product 和竞品池把每条路线补齐。"),
            NextActionOption("crawl_route_asins", "按路线抓评论", "每条保留路线单独进入评论导入和 VOC 分析。"),
            NextActionOption("adjust_route_asins", "调整路线批次", "运营可按路线增删竞品后再抓评论。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _voc_analysis_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=False,
        question="下一步导入评论插件数据，分析痛点、亮点和可验证机会。",
        recommended_action=RecommendedAction(
            "local_script",
            "导入评论 VOC",
            "评论数据进入结构化包后，AI 才能基于证据做痛点分析。",
        ),
        options=[
            NextActionOption("import_review_voc", "导入评论数据", "生成 review_voc_package。"),
            NextActionOption("crawl_more_reviews", "补抓评论", "样本不足时继续补证据。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _deep_dive_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=False,
        question="下一步先完成路线级小深挖，再选择 1-2 条证据最完整的路线进入正式深挖报告。已调过的 category_report / keyword_detail 直接复用。",
        recommended_action=RecommendedAction(
            "mcp_call",
            "路线级 Sorftime 深度验证",
            "每条保留路线都要有路线专属竞品流量词、竞品词包和 VOC 证据，避免过早只深挖单一款式。",
            mcp_tools=[
                {
                    "tool": "product_traffic_terms",
                    "purpose": "按路线查看重点竞品靠哪些词拿流量，找词位空隙",
                    "params_hint": "asin: 每条保留路线 Top2-3 代表 ASIN（逐个调用）",
                    "credits": 1,
                    "repeat": "每个路线代表 ASIN 各调一次，先标准款和升级路线",
                },
                {
                    "tool": "competitor_product_keywords",
                    "purpose": "提取路线代表竞品词包，判断不同路线是不是抢同一批流量",
                    "params_hint": "asin: 同 product_traffic_terms",
                    "credits": 1,
                    "repeat": "与 product_traffic_terms 搭配，优先同一批路线 ASIN",
                },
                {
                    "tool": "keyword_trend",
                    "purpose": "路线主词 24 个月趋势（已有 keyword_detail 时可跳过）",
                    "params_hint": "keyword: 每条路线 1-2 个主词",
                    "credits": 1,
                    "timing": "keyword_detail 未覆盖趋势数据时补调",
                },
                {
                    "tool": "similar_product_feature",
                    "purpose": "路线确认后看同类热销品共有特征，指导卖点提炼",
                    "params_hint": "productName: 已选主路线英文品类名",
                    "credits": 5,
                    "timing": "⚠️ 高积分，仅在选定 1-2 条主攻路线后调用，不给所有小众形态都调",
                },
            ],
        ),
        options=[
            NextActionOption("call_route_traffic_terms", "按路线调流量词", "补充卖家精灵看不到的路线流量结构。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _final_decision_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage="final_decision",
        decision_required=False,
        question="下一步生成市场分析报告，沉淀交互过程、证据链和继续看/谨慎继续/暂缓结论。",
        recommended_action=RecommendedAction(
            "render_report",
            "生成市场分析报告",
            "报告是市场证据链的沉淀，不是孤立自动生成的结论。",
        ),
        options=[
            NextActionOption("render_final_report", "生成报告", "输出 report/data。"),
            NextActionOption("continue_validation", "继续验证", "保留 Wait 并补下一步动作。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _next_stage(stage: WorkflowStage) -> WorkflowStage:
    index = STAGE_ORDER.index(stage)
    if index >= len(STAGE_ORDER) - 1:
        return "final_decision"
    return STAGE_ORDER[index + 1]


def _initial_missing_inputs(mode: WorkflowMode) -> list[str]:
    if mode == "broad_discovery":
        return ["运营探索边界", "候选方向确认", "卖家精灵大盘导出"]
    return ["产品边界确认", "卖家精灵 Top100/市场分析导出", "评论 VOC 数据"]


def _missing_inputs_for_stage(
    stage: WorkflowStage,
    mode: WorkflowMode,
    known_inputs: dict[str, Any],
) -> list[str]:
    required_by_stage: dict[WorkflowStage, list[str]] = {
        "seller_sprite_request": ["卖家精灵导出文件夹"],
        "data_inventory": ["import_manifest"],
        "candidate_pool_review": ["candidate_pool"],
        "boundary_confirmation": ["运营确认的标准形态/排除项"],
        "voc_batch_planning": ["VOC ASIN 批次确认"],
        "voc_analysis": ["评论插件导出数据"],
        "deep_dive": [],
        "final_decision": ["最终报告输出确认"],
    }
    missing = []
    for item in required_by_stage.get(stage, _initial_missing_inputs(mode)):
        key = _known_input_key(item)
        if key not in known_inputs:
            missing.append(item)
    return missing


def _known_input_key(label: str) -> str:
    mapping = {
        "卖家精灵导出文件夹": "seller_sprite_export_folder",
        "import_manifest": "import_manifest",
        "candidate_pool": "candidate_pool",
        "运营确认的标准形态/排除项": "confirmed_boundary",
        "VOC ASIN 批次确认": "review_asin_batch",
        "评论插件导出数据": "review_voc_package",
        "最终报告输出确认": "final_report",
    }
    return mapping.get(label, label)


def _refs_from_known_inputs(state: WorkflowState) -> list[EvidenceRef]:
    refs = []
    for key, value in state.known_inputs.items():
        if isinstance(value, str):
            refs.append(EvidenceRef(ref_type="known_input", ref_id=key, path=value))
        elif isinstance(value, dict):
            refs.append(EvidenceRef(ref_type="known_input", ref_id=key, note=str(value.get("note", ""))))
    return refs


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
