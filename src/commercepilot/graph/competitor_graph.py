from typing import Any

from langgraph.graph import END, START, StateGraph
from openai import OpenAI, OpenAIError

from commercepilot.core.config import get_settings
from commercepilot.db.session import SessionLocal
from commercepilot.graph.competitor_state import CompetitorAgentState
from commercepilot.services.competitor_analysis import (
    analyze_competitor_evidence,
)
from commercepilot.services.competitor_intelligence import (
    load_competitor_evidence,
)

LOAD_COMPETITOR_EVIDENCE_NODE = "load_competitor_evidence"
ANALYZE_COMPETITORS_NODE = "analyze_competitors"


def load_competitor_evidence_node(
    state: CompetitorAgentState,
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            evidence = load_competitor_evidence(
                session,
                state["product_sku"],
            )
    except ValueError as error:
        return {"evidence": None, "error": str(error)}

    return {"evidence": evidence, "error": None}


def analyze_competitors_node(
    state: CompetitorAgentState,
) -> dict[str, Any]:
    evidence = state["evidence"]
    if evidence is None:
        return {
            "insight": None,
            "error": "Competitor evidence is required before analysis.",
        }

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "insight": None,
            "error": "COMMERCEPILOT_OPENAI_API_KEY is not configured.",
        }

    try:
        insight = analyze_competitor_evidence(
            evidence,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )
    except (OpenAIError, ValueError) as error:
        return {"insight": None, "error": str(error)}

    return {"insight": insight, "error": None}


def route_after_loading_evidence(state: CompetitorAgentState) -> str:
    if state["error"] is not None:
        return END
    return ANALYZE_COMPETITORS_NODE


def build_competitor_graph() -> Any:
    graph = StateGraph(CompetitorAgentState)
    graph.add_node(
        LOAD_COMPETITOR_EVIDENCE_NODE,
        load_competitor_evidence_node,
    )
    graph.add_node(ANALYZE_COMPETITORS_NODE, analyze_competitors_node)
    graph.add_edge(START, LOAD_COMPETITOR_EVIDENCE_NODE)
    graph.add_conditional_edges(
        LOAD_COMPETITOR_EVIDENCE_NODE,
        route_after_loading_evidence,
        {
            ANALYZE_COMPETITORS_NODE: ANALYZE_COMPETITORS_NODE,
            END: END,
        },
    )
    graph.add_edge(ANALYZE_COMPETITORS_NODE, END)
    return graph.compile()
