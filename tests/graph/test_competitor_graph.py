from unittest.mock import MagicMock, patch

from commercepilot.graph.competitor_graph import (
    build_competitor_graph,
    load_competitor_evidence_node,
)
from commercepilot.graph.competitor_state import CompetitorAgentState


def initial_state() -> CompetitorAgentState:
    return CompetitorAgentState(
        product_sku="NOVA-AUDIO-001",
        evidence=None,
        insight=None,
        error=None,
    )


@patch("commercepilot.graph.competitor_graph.load_competitor_evidence")
@patch("commercepilot.graph.competitor_graph.SessionLocal")
def test_load_competitor_evidence_node_updates_state(
    session_factory: MagicMock,
    load_evidence: MagicMock,
) -> None:
    evidence = MagicMock()
    load_evidence.return_value = evidence
    session = session_factory.return_value.__enter__.return_value

    update = load_competitor_evidence_node(initial_state())

    load_evidence.assert_called_once_with(session, "NOVA-AUDIO-001")
    assert update == {"evidence": evidence, "error": None}


@patch("commercepilot.graph.competitor_graph.analyze_competitors_node")
@patch("commercepilot.graph.competitor_graph.load_competitor_evidence")
@patch("commercepilot.graph.competitor_graph.SessionLocal")
def test_competitor_graph_runs_from_start_to_end(
    session_factory: MagicMock,
    load_evidence: MagicMock,
    analyze_competitors: MagicMock,
) -> None:
    evidence = MagicMock()
    insight = MagicMock()
    load_evidence.return_value = evidence
    analyze_competitors.return_value = {
        "insight": insight,
        "error": None,
    }

    graph = build_competitor_graph()
    result = graph.invoke(initial_state())

    assert result["evidence"] is evidence
    assert result["insight"] is insight
    assert result["error"] is None
    session_factory.assert_called_once()
    analyze_competitors.assert_called_once()
