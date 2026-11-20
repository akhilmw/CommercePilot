from typing import Any

from langgraph.graph import END, START, StateGraph
from openai import OpenAI, OpenAIError

from commercepilot.core.config import get_settings
from commercepilot.db.session import SessionLocal
from commercepilot.graph.campaign_state import CampaignAgentState
from commercepilot.services.campaign_generation import generate_campaign_draft
from commercepilot.services.campaign_intelligence import load_campaign_evidence

LOAD_CAMPAIGN_EVIDENCE_NODE = "load_campaign_evidence"
GENERATE_CAMPAIGN_DRAFT_NODE = "generate_campaign_draft"


def load_campaign_evidence_node(
    state: CampaignAgentState,
) -> dict[str, Any]:
    review_insight = state["review_insight"]
    competitor_insight = state["competitor_insight"]
    strategy = state["strategy"]
    if review_insight is None or competitor_insight is None or strategy is None:
        return {
            "evidence": None,
            "error": (
                "Review insight, competitor insight, and strategy are required "
                "before campaign generation."
            ),
        }

    try:
        with SessionLocal() as session:
            evidence = load_campaign_evidence(
                session,
                state["product_sku"],
                review_insight,
                competitor_insight,
                strategy,
            )
    except ValueError as error:
        return {"evidence": None, "error": str(error)}

    return {"evidence": evidence, "error": None}


def generate_campaign_draft_node(
    state: CampaignAgentState,
) -> dict[str, Any]:
    evidence = state["evidence"]
    if evidence is None:
        return {
            "draft": None,
            "error": "Campaign evidence is required before draft generation.",
        }

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "draft": None,
            "error": "COMMERCEPILOT_OPENAI_API_KEY is not configured.",
        }

    try:
        draft = generate_campaign_draft(
            evidence,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )
    except (OpenAIError, ValueError) as error:
        return {"draft": None, "error": str(error)}

    return {"draft": draft, "error": None}


def route_after_loading_campaign_evidence(state: CampaignAgentState) -> str:
    if state["error"] is not None:
        return END
    return GENERATE_CAMPAIGN_DRAFT_NODE


def build_campaign_graph() -> Any:
    graph = StateGraph(CampaignAgentState)
    graph.add_node(
        LOAD_CAMPAIGN_EVIDENCE_NODE,
        load_campaign_evidence_node,
    )
    graph.add_node(
        GENERATE_CAMPAIGN_DRAFT_NODE,
        generate_campaign_draft_node,
    )
    graph.add_edge(START, LOAD_CAMPAIGN_EVIDENCE_NODE)
    graph.add_conditional_edges(
        LOAD_CAMPAIGN_EVIDENCE_NODE,
        route_after_loading_campaign_evidence,
        {
            GENERATE_CAMPAIGN_DRAFT_NODE: GENERATE_CAMPAIGN_DRAFT_NODE,
            END: END,
        },
    )
    graph.add_edge(GENERATE_CAMPAIGN_DRAFT_NODE, END)
    return graph.compile()
