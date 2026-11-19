from commercepilot.graph.review_state import ReviewAgentState


def test_review_agent_initial_state() -> None:
    state = ReviewAgentState(
        product_sku="NOVA-AUDIO-001",
        evidence=None,
        insight=None,
        error=None,
    )

    assert state["product_sku"] == "NOVA-AUDIO-001"
    assert state["evidence"] is None
    assert state["insight"] is None
    assert state["error"] is None
