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
    "profit_compliance_review",
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
    "profit_compliance_review",
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.action_type,
            "label": self.label,
            "reason": self.reason,
        }


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
    if state.stage == "profit_compliance_review":
        return _profit_compliance_review_card(state)
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
            question="请确认本轮无方向探索的业务边界：目标站点、禁做类目、价格/重量偏好。",
            recommended_action=RecommendedAction(
                "operator_decision",
                "确认探索边界",
                "方向仍然较宽，先确认边界再决定调 MCP 还是让运营导出大盘数据。",
            ),
            options=[
                NextActionOption("confirm_boundary", "确认边界", "进入方向拆解和类目探索。"),
                NextActionOption("add_constraints", "补充限制", "先补禁区、价格带、供应链优势。"),
            ],
        )
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请确认指定方向的产品边界：包含哪些形态，排除哪些混池场景？",
        recommended_action=RecommendedAction(
            "operator_decision",
            "确认产品边界",
            "指定方向深挖前必须先防止关键词和竞品混池。",
        ),
        options=[
            NextActionOption("confirm_product_boundary", "确认边界", "进入关键词/导出规划。"),
            NextActionOption("refine_product_boundary", "修正边界", "补充保留、排除、可参考场景。"),
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
                "调用 Sorftime broad/category",
                "当前还没有可落地导出关键词，先用低成本类目探索拆 2-4 个方向。",
            ),
            options=[
                NextActionOption("call_sorftime_broad", "先调 MCP 扫方向", "快速拆方向，避免盲导出。"),
                NextActionOption("request_market_export", "直接导出选市场 200 条", "适合运营已有明确类目入口。"),
            ],
        )
    return NextActionCard(
        stage=state.stage,
        decision_required=False,
        question="下一步生成卖家精灵导出清单，并可补一次关键词/趋势 MCP 验证。",
        recommended_action=RecommendedAction(
            "operator_export",
            "生成卖家精灵导出清单",
            "指定方向已明确，卖家精灵 Top100 和市场分析是正式深挖底座。",
        ),
        options=[
            NextActionOption("request_seller_sprite", "导出卖家精灵数据", "进入数据盘点和候选池预审。"),
            NextActionOption("call_keyword_mcp", "先调关键词趋势 MCP", "校验关键词是否值得导出。"),
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
        question="请选择本轮要进入深挖的候选方向，或先修正混池/排除规则。",
        recommended_action=RecommendedAction(
            "operator_decision",
            "确认深挖候选",
            "候选池可能包含主线、旁支和混池项，必须由运营确认资源投入方向。",
        ),
        options=[
            NextActionOption("deep_dive_candidate", "选择候选进入深挖", "进入边界确认和 VOC ASIN 规划。"),
            NextActionOption("refine_boundary", "先修正边界", "更新排除项后重新生成候选池。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _boundary_confirmation_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请确认主线、保留参考、排除项和可附带场景。",
        recommended_action=RecommendedAction(
            "operator_decision",
            "确认候选边界",
            "边界确认后才能给准确的 VOC ASIN 批次。",
        ),
        options=[
            NextActionOption("confirm_boundary", "确认边界", "进入 VOC ASIN 批次规划。"),
            NextActionOption("exclude_mixed_pool", "补充排除项", "避免抓错评论和竞品。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _voc_batch_planning_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="请确认评论抓取 ASIN 批次：标杆老品、新品、差评高发、功能差异和价格带代表。",
        recommended_action=RecommendedAction(
            "review_crawl",
            "抓取评论 VOC",
            "VOC 是真实痛点和改品机会的证据，不确认 ASIN 批次容易抓偏。",
        ),
        options=[
            NextActionOption("crawl_recommended_asins", "按推荐 ASIN 抓评论", "进入评论导入和 VOC 分析。"),
            NextActionOption("adjust_asin_batch", "调整 ASIN 批次", "运营可增删竞品后再抓评论。"),
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
        question="下一步综合市场、竞品、VOC，并按需要调用 Sorftime 深度验证。",
        recommended_action=RecommendedAction(
            "mcp_call",
            "做深度交叉验证",
            "正式结论需要卖家精灵、VOC 和 MCP 趋势/流量词相互印证。",
        ),
        options=[
            NextActionOption("call_competitor_keywords", "调竞品流量词 MCP", "补充卖家精灵看不到的流量结构。"),
            NextActionOption("build_research_package", "生成深挖数据包", "进入利润/合规和报告沉淀。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _profit_compliance_review_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage=state.stage,
        decision_required=True,
        question="是否补利润和知产/合规模板？未补齐时最终只能输出 Wait。",
        recommended_action=RecommendedAction(
            "operator_upload",
            "补利润/合规复核",
            "利润、知产和合规是 Go/No-Go 的硬门槛。",
        ),
        options=[
            NextActionOption("fill_profit_compliance", "填写并上传模板", "生成更完整的最终报告。"),
            NextActionOption("skip_and_wait", "暂不填写", "最终结论限制为 Wait/待补。"),
        ],
        evidence_refs=_refs_from_known_inputs(state),
    )


def _final_decision_card(state: WorkflowState) -> NextActionCard:
    return NextActionCard(
        stage="final_decision",
        decision_required=False,
        question="下一步生成最终报告，沉淀交互过程、证据链和 Go/Wait/No-Go 结论。",
        recommended_action=RecommendedAction(
            "render_report",
            "生成最终报告",
            "报告是交互过程的沉淀，不是孤立自动生成的结论。",
        ),
        options=[
            NextActionOption("render_final_report", "生成报告", "输出 report/summary/dashboard/data。"),
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
        "boundary_confirmation": ["运营确认的主线/排除项"],
        "voc_batch_planning": ["VOC ASIN 批次确认"],
        "voc_analysis": ["评论插件导出数据"],
        "deep_dive": ["research_package"],
        "profit_compliance_review": ["利润模板", "知产/合规模板"],
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
        "运营确认的主线/排除项": "confirmed_boundary",
        "VOC ASIN 批次确认": "review_asin_batch",
        "评论插件导出数据": "review_voc_package",
        "research_package": "research_package",
        "利润模板": "profit_template",
        "知产/合规模板": "ip_compliance_template",
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
