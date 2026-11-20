from unittest.mock import MagicMock, patch

from commercepilot.graph.campaign_graph import (
    build_campaign_graph,
    load_campaign_evidence_node,
)
from commercepilot.graph.campaign_state import CampaignAgentState


def initial_state() -> CampaignAgentState:
    return CampaignAgentState(
        product_sku="NOVA-AUDIO-001",
        review_insight=MagicMock(),
        competitor_insight=MagicMock(),
        strategy=MagicMock(),
        evidence=None,
        draft=None,
        error=None,
    )


@patch("commercepilot.graph.campaign_graph.load_campaign_evidence")
@patch("commercepilot.graph.campaign_graph.SessionLocal")
def test_load_campaign_evidence_node_updates_state(
    session_factory: MagicMock,
    load_evidence: MagicMock,
) -> None:
    state = initial_state()
    evidence = MagicMock()
    load_evidence.return_value = evidence
    session = session_factory.return_value.__enter__.return_value

    update = load_campaign_evidence_node(state)

    load_evidence.assert_called_once_with(
        session,
        "NOVA-AUDIO-001",
        state["review_insight"],
        state["competitor_insight"],
        state["strategy"],
    )
    assert update == {"evidence": evidence, "error": None}


def test_load_campaign_evidence_node_requires_all_inputs() -> None:
    state = initial_state()
    state["strategy"] = None

    update = load_campaign_evidence_node(state)

    assert update["evidence"] is None
    assert "strategy" in update["error"]


@patch("commercepilot.graph.campaign_graph.generate_campaign_draft_node")
@patch("commercepilot.graph.campaign_graph.load_campaign_evidence")
@patch("commercepilot.graph.campaign_graph.SessionLocal")
def test_campaign_graph_runs_from_start_to_end(
    session_factory: MagicMock,
    load_evidence: MagicMock,
    generate_draft: MagicMock,
) -> None:
    evidence = MagicMock()
    draft = MagicMock()
    load_evidence.return_value = evidence
    generate_draft.return_value = {"draft": draft, "error": None}

    result = build_campaign_graph().invoke(initial_state())

    assert result["evidence"] is evidence
    assert result["draft"] is draft
    assert result["error"] is None
    session_factory.assert_called_once()
    generate_draft.assert_called_once()
