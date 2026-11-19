from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from commercepilot.graph.orchestrator_graph import build_orchestrator_graph
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.models.enums import (
    ActionType,
    ImprovementPriority,
    SourceAgent,
)
from commercepilot.models.orchestration import (
    ActionProposal,
    CommerceStrategy,
    PriceChangeParameters,
)


def initial_state() -> CommercePilotState:
    return CommercePilotState(
        product_sku="NOVA-AUDIO-001",
        review_insight=None,
        competitor_insight=None,
        strategy=None,
        approval_policy=None,
        approval_decision=None,
        approved_action_ids=[],
        execution_results=[],
        review_error=None,
        competitor_error=None,
        error=None,
    )


@patch("commercepilot.graph.orchestrator_graph.synthesize_strategy_node")
@patch("commercepilot.graph.orchestrator_graph.run_competitor_agent_node")
@patch("commercepilot.graph.orchestrator_graph.run_review_agent_node")
def test_orchestrator_combines_agents_and_applies_policy(
    run_review: MagicMock,
    run_competitor: MagicMock,
    synthesize: MagicMock,
) -> None:
    review_insight = MagicMock()
    competitor_insight = MagicMock()
    strategy = CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary=(
            "Customer and competitor evidence support a coordinated response."
        ),
        strategic_objectives=["Protect conversion and product positioning."],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.DRAFT_CAMPAIGN,
                title="Draft a value-focused campaign",
                description="Prepare campaign copy about the product's value.",
                rationale="A competitor is currently priced below our product.",
                priority=ImprovementPriority.HIGH,
                source_agents=[SourceAgent.COMPETITOR],
                evidence_ids=[uuid4()],
            )
        ],
        confidence=0.8,
    )
    run_review.return_value = {
        "review_insight": review_insight,
        "review_error": None,
    }
    run_competitor.return_value = {
        "competitor_insight": competitor_insight,
        "competitor_error": None,
    }
    synthesize.return_value = {"strategy": strategy, "error": None}

    result = build_orchestrator_graph().invoke(initial_state())

    assert result["review_insight"] is review_insight
    assert result["competitor_insight"] is competitor_insight
    assert result["strategy"] == strategy
    assert result["approval_policy"] is not None
    assert result["approval_policy"].requires_human_approval is False
    assert result["approval_decision"] is None
    assert result["error"] is None
    run_review.assert_called_once()
    run_competitor.assert_called_once()
    synthesize.assert_called_once()


@pytest.mark.asyncio
@patch("commercepilot.graph.orchestrator_graph.execute_approved_actions_node")
@patch("commercepilot.graph.orchestrator_graph.persist_approved_actions_node")
@patch("commercepilot.graph.orchestrator_graph.synthesize_strategy_node")
@patch("commercepilot.graph.orchestrator_graph.run_competitor_agent_node")
@patch("commercepilot.graph.orchestrator_graph.run_review_agent_node")
async def test_orchestrator_pauses_and_resumes_for_human_approval(
    run_review: MagicMock,
    run_competitor: MagicMock,
    synthesize: MagicMock,
    persist_actions: MagicMock,
    execute_actions: MagicMock,
) -> None:
    strategy = CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary=(
            "Current market evidence supports evaluating a temporary response."
        ),
        strategic_objectives=["Protect conversion during competitor promotion."],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.CHANGE_PRICE,
                title="Consider a temporary price change",
                description="Temporarily narrow the current competitor price gap.",
                rationale="A competitor is currently priced below our product.",
                priority=ImprovementPriority.HIGH,
                source_agents=[SourceAgent.COMPETITOR],
                evidence_ids=[uuid4()],
                price_change=PriceChangeParameters(
                    sku="NOVA-AUDIO-001",
                    expected_current_price=Decimal("129.99"),
                    new_price=Decimal("119.99"),
                ),
            )
        ],
        confidence=0.8,
    )
    run_review.return_value = {
        "review_insight": None,
        "review_error": None,
    }
    run_competitor.return_value = {
        "competitor_insight": None,
        "competitor_error": None,
    }
    synthesize.return_value = {"strategy": strategy, "error": None}
    action_id = uuid4()
    persist_actions.return_value = {
        "approved_action_ids": [action_id],
        "error": None,
    }
    execute_actions.return_value = {
        "execution_results": [],
        "error": None,
    }

    graph = build_orchestrator_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "approval-test"}}
    interrupted = await graph.ainvoke(initial_state(), config=config)

    assert interrupted["approval_decision"] is None
    assert len(interrupted["__interrupt__"]) == 1
    payload = interrupted["__interrupt__"][0].value
    assert payload["type"] == "human_approval_required"
    assert payload["actions"][0]["action_type"] == "change_price"

    completed = await graph.ainvoke(
        Command(
            resume={
                "approved": True,
                "reviewer": "test-user",
                "comment": "Approved for test.",
            }
        ),
        config=config,
    )

    assert completed["approval_decision"] is not None
    assert completed["approval_decision"].approved is True
    assert completed["approval_decision"].reviewer == "test-user"
    persist_actions.assert_called_once()
    execute_actions.assert_called_once()
