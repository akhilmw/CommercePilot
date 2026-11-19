from typing import Any

from langgraph.graph import END, START, StateGraph
from openai import OpenAI, OpenAIError

from commercepilot.core.config import get_settings
from commercepilot.db.session import SessionLocal
from commercepilot.graph.review_state import ReviewAgentState
from commercepilot.services.review_analysis import analyze_review_evidence
from commercepilot.services.review_intelligence import load_review_evidence

LOAD_REVIEW_EVIDENCE_NODE = "load_review_evidence"
ANALYZE_REVIEWS_NODE = "analyze_reviews"


def load_review_evidence_node(
    state: ReviewAgentState,
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            evidence = load_review_evidence(session, state["product_sku"])
    except ValueError as error:
        return {
            "evidence": None,
            "error": str(error),
        }

    return {
        "evidence": evidence,
        "error": None,
    }


def analyze_reviews_node(
    state: ReviewAgentState,
) -> dict[str, Any]:
    evidence = state["evidence"]
    if evidence is None:
        return {
            "insight": None,
            "error": "Review evidence is required before analysis.",
        }

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "insight": None,
            "error": "COMMERCEPILOT_OPENAI_API_KEY is not configured.",
        }

    try:
        insight = analyze_review_evidence(
            evidence,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )
    except (OpenAIError, ValueError) as error:
        return {
            "insight": None,
            "error": str(error),
        }

    return {
        "insight": insight,
        "error": None,
    }


def route_after_loading_evidence(state: ReviewAgentState) -> str:
    if state["error"] is not None:
        return END
    return ANALYZE_REVIEWS_NODE


def build_review_graph() -> Any:
    graph = StateGraph(ReviewAgentState)
    graph.add_node(LOAD_REVIEW_EVIDENCE_NODE, load_review_evidence_node)
    graph.add_node(ANALYZE_REVIEWS_NODE, analyze_reviews_node)
    graph.add_edge(START, LOAD_REVIEW_EVIDENCE_NODE)
    graph.add_conditional_edges(
        LOAD_REVIEW_EVIDENCE_NODE,
        route_after_loading_evidence,
        {
            ANALYZE_REVIEWS_NODE: ANALYZE_REVIEWS_NODE,
            END: END,
        },
    )
    graph.add_edge(ANALYZE_REVIEWS_NODE, END)
    return graph.compile()
