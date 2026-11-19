from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from openai import OpenAI, OpenAIError

from commercepilot.core.config import get_settings
from commercepilot.graph.competitor_graph import build_competitor_graph
from commercepilot.graph.competitor_state import CompetitorAgentState
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.graph.review_graph import build_review_graph
from commercepilot.graph.review_state import ReviewAgentState
from commercepilot.models.orchestration import HumanApprovalDecision
from commercepilot.services.approval_policy import apply_approval_policy
from commercepilot.services.strategy_synthesis import synthesize_strategy

RUN_REVIEW_AGENT_NODE = "run_review_agent"
RUN_COMPETITOR_AGENT_NODE = "run_competitor_agent"
SYNTHESIZE_STRATEGY_NODE = "synthesize_strategy"
APPLY_APPROVAL_POLICY_NODE = "apply_approval_policy"
REQUEST_HUMAN_APPROVAL_NODE = "request_human_approval"


def run_review_agent_node(state: CommercePilotState) -> dict[str, Any]:
    graph = build_review_graph()
    result = graph.invoke(
        ReviewAgentState(
            product_sku=state["product_sku"],
            evidence=None,
            insight=None,
            error=None,
        )
    )
    return {
        "review_insight": result["insight"],
        "review_error": result["error"],
    }


def run_competitor_agent_node(state: CommercePilotState) -> dict[str, Any]:
    graph = build_competitor_graph()
    result = graph.invoke(
        CompetitorAgentState(
            product_sku=state["product_sku"],
            evidence=None,
            insight=None,
            error=None,
        )
    )
    return {
        "competitor_insight": result["insight"],
        "competitor_error": result["error"],
    }


def synthesize_strategy_node(state: CommercePilotState) -> dict[str, Any]:
    if state["review_error"] is not None:
        return {"strategy": None, "error": state["review_error"]}
    if state["competitor_error"] is not None:
        return {"strategy": None, "error": state["competitor_error"]}

    review_insight = state["review_insight"]
    competitor_insight = state["competitor_insight"]
    if review_insight is None or competitor_insight is None:
        return {
            "strategy": None,
            "error": "Both specialized agent insights are required.",
        }

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "strategy": None,
            "error": "COMMERCEPILOT_OPENAI_API_KEY is not configured.",
        }

    try:
        strategy = synthesize_strategy(
            review_insight,
            competitor_insight,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )
    except (OpenAIError, ValueError) as error:
        return {"strategy": None, "error": str(error)}

    return {"strategy": strategy, "error": None}


def apply_approval_policy_node(state: CommercePilotState) -> dict[str, Any]:
    strategy = state["strategy"]
    if strategy is None:
        return {
            "approval_policy": None,
            "error": "A strategy is required before applying approval policy.",
        }

    return {
        "approval_policy": apply_approval_policy(strategy.action_proposals),
        "error": None,
    }


def request_human_approval_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    policy = state["approval_policy"]
    if policy is None:
        return {
            "approval_decision": None,
            "error": "Approval policy is required before requesting approval.",
        }

    pending_actions = [
        action.model_dump(mode="json")
        for action in policy.actions
        if action.requires_human_approval
    ]
    decision = interrupt(
        {
            "type": "human_approval_required",
            "product_sku": state["product_sku"],
            "actions": pending_actions,
        }
    )

    return {
        "approval_decision": HumanApprovalDecision.model_validate(decision),
        "error": None,
    }


def route_after_synthesis(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return APPLY_APPROVAL_POLICY_NODE


def route_after_approval_policy(state: CommercePilotState) -> str:
    policy = state["approval_policy"]
    if state["error"] is not None or policy is None:
        return END
    if policy.requires_human_approval:
        return REQUEST_HUMAN_APPROVAL_NODE
    return END


def build_orchestrator_graph(checkpointer: Any | None = None) -> Any:
    graph = StateGraph(CommercePilotState)
    graph.add_node(RUN_REVIEW_AGENT_NODE, run_review_agent_node)
    graph.add_node(RUN_COMPETITOR_AGENT_NODE, run_competitor_agent_node)
    graph.add_node(SYNTHESIZE_STRATEGY_NODE, synthesize_strategy_node)
    graph.add_node(
        APPLY_APPROVAL_POLICY_NODE,
        apply_approval_policy_node,
    )
    graph.add_node(
        REQUEST_HUMAN_APPROVAL_NODE,
        request_human_approval_node,
    )

    graph.add_edge(START, RUN_REVIEW_AGENT_NODE)
    graph.add_edge(START, RUN_COMPETITOR_AGENT_NODE)
    graph.add_edge(
        [RUN_REVIEW_AGENT_NODE, RUN_COMPETITOR_AGENT_NODE],
        SYNTHESIZE_STRATEGY_NODE,
    )
    graph.add_conditional_edges(
        SYNTHESIZE_STRATEGY_NODE,
        route_after_synthesis,
        {
            APPLY_APPROVAL_POLICY_NODE: APPLY_APPROVAL_POLICY_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        APPLY_APPROVAL_POLICY_NODE,
        route_after_approval_policy,
        {
            REQUEST_HUMAN_APPROVAL_NODE: REQUEST_HUMAN_APPROVAL_NODE,
            END: END,
        },
    )
    graph.add_edge(REQUEST_HUMAN_APPROVAL_NODE, END)
    return graph.compile(checkpointer=checkpointer)
