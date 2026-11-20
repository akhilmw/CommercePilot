from unittest.mock import MagicMock, patch

from commercepilot.graph.catalog_graph import (
    build_catalog_graph,
    load_catalog_evidence_node,
)
from commercepilot.graph.catalog_state import CatalogAgentState


def initial_state() -> CatalogAgentState:
    return CatalogAgentState(
        product_sku="NOVA-AUDIO-001",
        review_insight=MagicMock(),
        competitor_insight=MagicMock(),
        evidence=None,
        draft=None,
        error=None,
    )


@patch("commercepilot.graph.catalog_graph.load_catalog_evidence")
@patch("commercepilot.graph.catalog_graph.SessionLocal")
def test_load_catalog_evidence_node_updates_state(
    session_factory: MagicMock,
    load_evidence: MagicMock,
) -> None:
    state = initial_state()
    evidence = MagicMock()
    load_evidence.return_value = evidence
    session = session_factory.return_value.__enter__.return_value

    update = load_catalog_evidence_node(state)

    load_evidence.assert_called_once_with(
        session,
        "NOVA-AUDIO-001",
        state["review_insight"],
        state["competitor_insight"],
    )
    assert update == {"evidence": evidence, "error": None}


def test_load_catalog_evidence_node_requires_both_agent_insights() -> None:
    state = initial_state()
    state["review_insight"] = None

    update = load_catalog_evidence_node(state)

    assert update["evidence"] is None
    assert "Review and competitor insights" in update["error"]


@patch("commercepilot.graph.catalog_graph.generate_catalog_draft_node")
@patch("commercepilot.graph.catalog_graph.load_catalog_evidence")
@patch("commercepilot.graph.catalog_graph.SessionLocal")
def test_catalog_graph_runs_from_start_to_end(
    session_factory: MagicMock,
    load_evidence: MagicMock,
    generate_draft: MagicMock,
) -> None:
    evidence = MagicMock()
    draft = MagicMock()
    load_evidence.return_value = evidence
    generate_draft.return_value = {"draft": draft, "error": None}

    result = build_catalog_graph().invoke(initial_state())

    assert result["evidence"] is evidence
    assert result["draft"] is draft
    assert result["error"] is None
    session_factory.assert_called_once()
    generate_draft.assert_called_once()
