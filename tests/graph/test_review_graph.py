from unittest.mock import MagicMock, patch

from commercepilot.graph.review_graph import (
    build_review_graph,
    load_review_evidence_node,
)
from commercepilot.graph.review_state import ReviewAgentState


def initial_state(product_sku: str = "NOVA-AUDIO-001") -> ReviewAgentState:
    return ReviewAgentState(
        product_sku=product_sku,
        evidence=None,
        insight=None,
        error=None,
    )


@patch("commercepilot.graph.review_graph.load_review_evidence")
@patch("commercepilot.graph.review_graph.SessionLocal")
def test_load_review_evidence_node_updates_graph_state(
    session_factory: MagicMock,
    load_evidence: MagicMock,
) -> None:
    evidence = MagicMock()
    load_evidence.return_value = evidence
    session = session_factory.return_value.__enter__.return_value

    update = load_review_evidence_node(initial_state())

    load_evidence.assert_called_once_with(session, "NOVA-AUDIO-001")
    assert update == {"evidence": evidence, "error": None}


@patch("commercepilot.graph.review_graph.load_review_evidence")
@patch("commercepilot.graph.review_graph.SessionLocal")
def test_load_review_evidence_node_captures_unknown_product(
    session_factory: MagicMock,
    load_evidence: MagicMock,
) -> None:
    load_evidence.side_effect = ValueError("Unknown product SKU: UNKNOWN-SKU")

    update = load_review_evidence_node(initial_state("UNKNOWN-SKU"))

    assert update["evidence"] is None
    assert update["error"] == "Unknown product SKU: UNKNOWN-SKU"
    session_factory.assert_called_once()


@patch("commercepilot.graph.review_graph.analyze_reviews_node")
@patch("commercepilot.graph.review_graph.load_review_evidence")
@patch("commercepilot.graph.review_graph.SessionLocal")
def test_review_graph_runs_from_start_to_end(
    session_factory: MagicMock,
    load_evidence: MagicMock,
    analyze_reviews: MagicMock,
) -> None:
    evidence = MagicMock()
    insight = MagicMock()
    load_evidence.return_value = evidence
    analyze_reviews.return_value = {
        "insight": insight,
        "error": None,
    }

    review_graph = build_review_graph()
    result = review_graph.invoke(initial_state())

    assert result["product_sku"] == "NOVA-AUDIO-001"
    assert result["evidence"] is evidence
    assert result["insight"] is insight
    assert result["error"] is None
    session_factory.assert_called_once()
    analyze_reviews.assert_called_once()
