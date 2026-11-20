from typing import Any

from langgraph.graph import END, START, StateGraph
from openai import OpenAI, OpenAIError

from commercepilot.core.config import get_settings
from commercepilot.db.session import SessionLocal
from commercepilot.graph.catalog_state import CatalogAgentState
from commercepilot.services.catalog_generation import generate_catalog_draft
from commercepilot.services.catalog_intelligence import load_catalog_evidence

LOAD_CATALOG_EVIDENCE_NODE = "load_catalog_evidence"
GENERATE_CATALOG_DRAFT_NODE = "generate_catalog_draft"


def load_catalog_evidence_node(
    state: CatalogAgentState,
) -> dict[str, Any]:
    review_insight = state["review_insight"]
    competitor_insight = state["competitor_insight"]
    if review_insight is None or competitor_insight is None:
        return {
            "evidence": None,
            "error": (
                "Review and competitor insights are required before catalog "
                "generation."
            ),
        }

    try:
        with SessionLocal() as session:
            evidence = load_catalog_evidence(
                session,
                state["product_sku"],
                review_insight,
                competitor_insight,
            )
    except ValueError as error:
        return {"evidence": None, "error": str(error)}

    return {"evidence": evidence, "error": None}


def generate_catalog_draft_node(
    state: CatalogAgentState,
) -> dict[str, Any]:
    evidence = state["evidence"]
    if evidence is None:
        return {
            "draft": None,
            "error": "Catalog evidence is required before draft generation.",
        }

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "draft": None,
            "error": "COMMERCEPILOT_OPENAI_API_KEY is not configured.",
        }

    try:
        draft = generate_catalog_draft(
            evidence,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )
    except (OpenAIError, ValueError) as error:
        return {"draft": None, "error": str(error)}

    return {"draft": draft, "error": None}


def route_after_loading_catalog_evidence(state: CatalogAgentState) -> str:
    if state["error"] is not None:
        return END
    return GENERATE_CATALOG_DRAFT_NODE


def build_catalog_graph() -> Any:
    graph = StateGraph(CatalogAgentState)
    graph.add_node(
        LOAD_CATALOG_EVIDENCE_NODE,
        load_catalog_evidence_node,
    )
    graph.add_node(
        GENERATE_CATALOG_DRAFT_NODE,
        generate_catalog_draft_node,
    )
    graph.add_edge(START, LOAD_CATALOG_EVIDENCE_NODE)
    graph.add_conditional_edges(
        LOAD_CATALOG_EVIDENCE_NODE,
        route_after_loading_catalog_evidence,
        {
            GENERATE_CATALOG_DRAFT_NODE: GENERATE_CATALOG_DRAFT_NODE,
            END: END,
        },
    )
    graph.add_edge(GENERATE_CATALOG_DRAFT_NODE, END)
    return graph.compile()
