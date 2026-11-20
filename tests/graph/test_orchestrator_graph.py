from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from commercepilot.graph.checkpoint import build_orchestrator_checkpointer
from commercepilot.graph.orchestrator_graph import (
    RUN_CAMPAIGN_AGENT_NODE,
    RUN_CATALOG_AGENT_NODE,
    build_catalog_comparison_node,
    build_orchestrator_graph,
    execute_campaign_launch_node,
    execute_catalog_publish_node,
    persist_catalog_draft_node,
    process_catalog_approval_node,
    request_campaign_approval_node,
    request_catalog_approval_node,
    route_after_synthesis,
)
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.mcp.client import LaunchCampaignResult, PublishCatalogUpdateResult
from commercepilot.models.campaign import CampaignAsset, CampaignLaunchPreview
from commercepilot.models.catalog import CatalogComparison, CatalogFieldDiff
from commercepilot.models.enums import (
    ActionType,
    CampaignChannel,
    CampaignDraftStatus,
    CatalogDraftStatus,
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
        force_catalog_update=False,
        force_campaign_update=False,
        review_insight=None,
        competitor_insight=None,
        strategy=None,
        catalog_draft=None,
        catalog_draft_id=None,
        catalog_comparison=None,
        catalog_approval_decision=None,
        catalog_publish_action_id=None,
        catalog_execution_result=None,
        campaign_evidence=None,
        campaign_draft=None,
        campaign_draft_id=None,
        campaign_preview=None,
        campaign_approval_decision=None,
        campaign_launch_action_id=None,
        campaign_execution_result=None,
        approval_policy=None,
        approval_decision=None,
        approved_action_ids=[],
        execution_results=[],
        review_error=None,
        competitor_error=None,
        catalog_error=None,
        campaign_error=None,
        error=None,
    )


def test_force_catalog_routes_to_catalog_agent() -> None:
    state = initial_state()
    state["force_catalog_update"] = True
    state["strategy"] = CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary=(
            "Current evidence supports continued monitoring of the product."
        ),
        strategic_objectives=["Continue monitoring customer feedback."],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.DRAFT_CAMPAIGN,
                title="Draft an evidence-backed campaign",
                description="Prepare campaign copy from validated evidence.",
                rationale="Current evidence supports testing new messaging.",
                priority=ImprovementPriority.MEDIUM,
                source_agents=[SourceAgent.REVIEW],
                evidence_ids=[uuid4()],
            )
        ],
        confidence=0.8,
    )

    assert route_after_synthesis(state) == RUN_CATALOG_AGENT_NODE


def test_force_campaign_routes_to_campaign_agent() -> None:
    state = initial_state()
    state["force_campaign_update"] = True
    state["strategy"] = CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary="Evidence supports testing campaign messaging.",
        strategic_objectives=["Test evidence-backed positioning."],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.MONITOR_COMPETITORS,
                title="Continue competitor monitoring",
                description="Track positioning and price changes.",
                rationale="Ongoing monitoring supports future decisions.",
                priority=ImprovementPriority.LOW,
                source_agents=[SourceAgent.COMPETITOR],
                evidence_ids=[uuid4()],
            )
        ],
        confidence=0.8,
    )

    assert route_after_synthesis(state) == RUN_CAMPAIGN_AGENT_NODE


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
                action_type=ActionType.MONITOR_COMPETITORS,
                title="Monitor competitor positioning",
                description="Continue monitoring competitor positioning.",
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


@pytest.mark.asyncio
@patch("commercepilot.graph.orchestrator_graph.execute_catalog_publish_node")
@patch("commercepilot.graph.orchestrator_graph.process_catalog_approval_node")
@patch("commercepilot.graph.orchestrator_graph.request_catalog_approval_node")
@patch("commercepilot.graph.orchestrator_graph.build_catalog_comparison_node")
@patch("commercepilot.graph.orchestrator_graph.persist_catalog_draft_node")
@patch("commercepilot.graph.orchestrator_graph.run_catalog_agent_node")
@patch("commercepilot.graph.orchestrator_graph.synthesize_strategy_node")
@patch("commercepilot.graph.orchestrator_graph.run_competitor_agent_node")
@patch("commercepilot.graph.orchestrator_graph.run_review_agent_node")
async def test_orchestrator_runs_catalog_agent_for_catalog_draft_action(
    run_review: MagicMock,
    run_competitor: MagicMock,
    synthesize: MagicMock,
    run_catalog: MagicMock,
    persist_draft: MagicMock,
    build_comparison: MagicMock,
    request_catalog_approval: MagicMock,
    process_catalog_approval: MagicMock,
    execute_catalog_publish: AsyncMock,
) -> None:
    evidence_id = uuid4()
    strategy = CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary=(
            "Customer evidence supports an improved product listing draft."
        ),
        strategic_objectives=["Improve evidence-backed product positioning."],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.DRAFT_CATALOG_UPDATE,
                title="Draft an evidence-backed catalog update",
                description=(
                    "Prepare revised product copy grounded in customer evidence."
                ),
                rationale=(
                    "The current listing does not emphasize validated strengths."
                ),
                priority=ImprovementPriority.MEDIUM,
                source_agents=[SourceAgent.REVIEW],
                evidence_ids=[evidence_id],
            )
        ],
        confidence=0.84,
    )
    review_insight = MagicMock()
    competitor_insight = MagicMock()
    draft = MagicMock()
    run_review.return_value = {
        "review_insight": review_insight,
        "review_error": None,
    }
    run_competitor.return_value = {
        "competitor_insight": competitor_insight,
        "competitor_error": None,
    }
    synthesize.return_value = {"strategy": strategy, "error": None}
    run_catalog.return_value = {
        "catalog_draft": draft,
        "catalog_error": None,
        "error": None,
    }
    draft_id = uuid4()
    persist_draft.return_value = {
        "catalog_draft_id": draft_id,
        "catalog_error": None,
        "error": None,
    }
    comparison = MagicMock(spec=CatalogComparison)
    build_comparison.return_value = {
        "catalog_comparison": comparison,
        "catalog_error": None,
        "error": None,
    }
    request_catalog_approval.return_value = {
        "catalog_approval_decision": MagicMock(approved=True),
        "catalog_error": None,
        "error": None,
    }
    publish_action_id = uuid4()
    process_catalog_approval.return_value = {
        "catalog_publish_action_id": publish_action_id,
        "catalog_error": None,
        "error": None,
    }
    execution_result = MagicMock(spec=PublishCatalogUpdateResult)
    execute_catalog_publish.return_value = {
        "catalog_execution_result": execution_result,
        "catalog_error": None,
        "error": None,
    }

    result = await build_orchestrator_graph().ainvoke(initial_state())

    assert result["catalog_draft"] is draft
    assert result["catalog_draft_id"] == draft_id
    assert result["catalog_comparison"] is comparison
    assert result["catalog_publish_action_id"] == publish_action_id
    assert result["catalog_execution_result"] is execution_result
    assert result["catalog_error"] is None
    assert result["approval_policy"] is not None
    assert result["approval_policy"].requires_human_approval is False
    run_catalog.assert_called_once()
    persist_draft.assert_called_once()
    build_comparison.assert_called_once()
    request_catalog_approval.assert_called_once()
    process_catalog_approval.assert_called_once()
    execute_catalog_publish.assert_awaited_once()


@patch("commercepilot.graph.orchestrator_graph.save_catalog_draft")
@patch("commercepilot.graph.orchestrator_graph.SessionLocal")
def test_persist_catalog_draft_node_stores_id_in_graph_state(
    session_factory: MagicMock,
    save_draft: MagicMock,
) -> None:
    state = initial_state()
    state["catalog_draft"] = MagicMock()
    record = MagicMock()
    record.id = uuid4()
    save_draft.return_value = record
    session = session_factory.return_value.__enter__.return_value

    update = persist_catalog_draft_node(state)

    save_draft.assert_called_once_with(session, state["catalog_draft"])
    assert update == {
        "catalog_draft_id": record.id,
        "catalog_error": None,
        "error": None,
    }


def test_persist_catalog_draft_node_requires_validated_draft() -> None:
    update = persist_catalog_draft_node(initial_state())

    assert update["catalog_draft_id"] is None
    assert "validated catalog draft" in update["error"]


@patch("commercepilot.graph.orchestrator_graph.build_catalog_comparison")
@patch("commercepilot.graph.orchestrator_graph.SessionLocal")
def test_build_catalog_comparison_node_stores_comparison_in_state(
    session_factory: MagicMock,
    build_comparison: MagicMock,
) -> None:
    state = initial_state()
    state["catalog_draft_id"] = uuid4()
    comparison = MagicMock(spec=CatalogComparison)
    build_comparison.return_value = comparison
    session = session_factory.return_value.__enter__.return_value

    update = build_catalog_comparison_node(state)

    build_comparison.assert_called_once_with(
        session,
        state["catalog_draft_id"],
    )
    assert update == {
        "catalog_comparison": comparison,
        "catalog_error": None,
        "error": None,
    }


def test_request_catalog_approval_rejects_stale_comparison() -> None:
    state = initial_state()
    state["catalog_comparison"] = CatalogComparison(
        draft_id=uuid4(),
        product_id=uuid4(),
        product_sku="NOVA-AUDIO-001",
        status=CatalogDraftStatus.DRAFT,
        current_catalog_version=2,
        expected_catalog_version=1,
        is_stale=True,
        fields=[
            CatalogFieldDiff(
                field="seo_title",
                label="SEO title",
                current_value="NovaSound Pro",
                proposed_value="NovaSound Pro Wireless ANC Headphones",
                changed=True,
            )
        ],
    )

    update = request_catalog_approval_node(state)

    assert update["catalog_approval_decision"] is None
    assert "expected version 1, current version 2" in update["error"]


@pytest.mark.asyncio
async def test_catalog_rejection_resumes_from_serialized_checkpoint() -> None:
    state = initial_state()
    draft_id = uuid4()
    product_id = uuid4()
    state["catalog_comparison"] = CatalogComparison(
        draft_id=draft_id,
        product_id=product_id,
        product_sku="NOVA-AUDIO-001",
        status=CatalogDraftStatus.DRAFT,
        current_catalog_version=1,
        expected_catalog_version=1,
        is_stale=False,
        fields=[
            CatalogFieldDiff(
                field="seo_title",
                label="SEO title",
                current_value="NovaSound Pro",
                proposed_value="NovaSound Pro Wireless ANC Headphones",
                changed=True,
            )
        ],
    )

    builder = StateGraph(CommercePilotState)
    builder.add_node("request_catalog_approval", request_catalog_approval_node)
    builder.add_edge(START, "request_catalog_approval")
    builder.add_edge("request_catalog_approval", END)
    graph = builder.compile(checkpointer=build_orchestrator_checkpointer())
    config: RunnableConfig = {"configurable": {"thread_id": "catalog-rejection-test"}}

    interrupted = await graph.ainvoke(state, config=config)
    assert interrupted["__interrupt__"][0].value["draft_id"] == str(draft_id)

    completed = await graph.ainvoke(
        Command(
            resume={
                "approved": False,
                "reviewer": "test-user",
                "comment": "Unsupported catalog claim.",
            }
        ),
        config=config,
    )

    decision = completed["catalog_approval_decision"]
    assert decision is not None
    assert decision.approved is False
    assert decision.comment == "Unsupported catalog claim."


@pytest.mark.asyncio
async def test_campaign_rejection_resumes_from_serialized_checkpoint() -> None:
    state = initial_state()
    draft_id = uuid4()
    product_id = uuid4()
    evidence_id = uuid4()
    state["campaign_preview"] = CampaignLaunchPreview(
        draft_id=draft_id,
        product_id=product_id,
        product_sku="NOVA-AUDIO-001",
        status=CampaignDraftStatus.DRAFT,
        source_catalog_version=3,
        current_catalog_version=3,
        source_price=Decimal("99.99"),
        current_price=Decimal("99.99"),
        is_stale=False,
        name="NovaSound Commuter Campaign",
        objective="Increase qualified visits from daily commuters.",
        target_audience="Commuters seeking focused wireless listening.",
        core_message="Balanced sound and long battery life for daily travel.",
        assets=[
            CampaignAsset(
                channel=CampaignChannel.SOCIAL,
                headline="Sound made for the daily journey",
                body="Balanced wireless sound for focused daily travel.",
                call_to_action="Explore NovaSound Pro",
                evidence_ids=[evidence_id],
            )
        ],
        duration_days=21,
        success_metrics=["Click-through rate"],
        confidence=Decimal("0.85"),
    )

    builder = StateGraph(CommercePilotState)
    builder.add_node("request_campaign_approval", request_campaign_approval_node)
    builder.add_edge(START, "request_campaign_approval")
    builder.add_edge("request_campaign_approval", END)
    graph = builder.compile(checkpointer=build_orchestrator_checkpointer())
    config: RunnableConfig = {"configurable": {"thread_id": "campaign-rejection"}}

    interrupted = await graph.ainvoke(state, config=config)
    assert interrupted["__interrupt__"][0].value["draft_id"] == str(draft_id)

    completed = await graph.ainvoke(
        Command(
            resume={
                "approved": False,
                "reviewer": "test-user",
                "comment": "Campaign timing is not approved.",
            }
        ),
        config=config,
    )

    decision = completed["campaign_approval_decision"]
    assert decision is not None
    assert decision.approved is False
    assert decision.comment == "Campaign timing is not approved."


@patch("commercepilot.graph.orchestrator_graph.process_catalog_approval")
@patch("commercepilot.graph.orchestrator_graph.SessionLocal")
def test_process_catalog_approval_node_stores_approved_action_id(
    session_factory: MagicMock,
    process_approval: MagicMock,
) -> None:
    state = initial_state()
    state["catalog_draft_id"] = uuid4()
    state["catalog_approval_decision"] = MagicMock(approved=True)
    action = MagicMock()
    action.id = uuid4()
    process_approval.return_value = action
    session = session_factory.return_value.__enter__.return_value

    update = process_catalog_approval_node(state)

    process_approval.assert_called_once_with(
        session,
        state["catalog_draft_id"],
        state["catalog_approval_decision"],
    )
    assert update == {
        "catalog_publish_action_id": action.id,
        "catalog_error": None,
        "error": None,
    }


@patch("commercepilot.graph.orchestrator_graph.process_catalog_approval")
@patch("commercepilot.graph.orchestrator_graph.SessionLocal")
def test_process_catalog_rejection_creates_no_action_id(
    session_factory: MagicMock,
    process_approval: MagicMock,
) -> None:
    state = initial_state()
    state["catalog_draft_id"] = uuid4()
    state["catalog_approval_decision"] = MagicMock(approved=False)
    process_approval.return_value = None

    update = process_catalog_approval_node(state)

    assert update == {
        "catalog_publish_action_id": None,
        "catalog_error": None,
        "error": None,
    }


@pytest.mark.asyncio
@patch("commercepilot.graph.orchestrator_graph.CommercePilotMCPClient")
@patch("commercepilot.graph.orchestrator_graph.SessionLocal")
async def test_execute_catalog_publish_node_calls_mcp_with_approved_identifiers(
    session_factory: MagicMock,
    client_factory: MagicMock,
) -> None:
    state = initial_state()
    action_id = uuid4()
    state["catalog_publish_action_id"] = action_id
    action = MagicMock()
    action.id = action_id
    action.action_type = "publish_catalog_update"
    action.idempotency_key = f"catalog-publish:{action_id}"
    action.payload = {
        "draft_id": str(action_id),
        "product_sku": "NOVA-AUDIO-001",
        "expected_catalog_version": 1,
    }
    session_factory.return_value.__enter__.return_value.get.return_value = action
    execution = PublishCatalogUpdateResult(
        status="executed",
        action_id=str(action_id),
        draft_id=str(action_id),
        sku="NOVA-AUDIO-001",
        previous_catalog_version=1,
        current_catalog_version=2,
        published_at="2026-11-19T23:00:00Z",
        replayed=False,
    )
    client = client_factory.return_value
    client.publish_catalog_update = AsyncMock(return_value=execution)

    update = await execute_catalog_publish_node(state)

    awaited_call = client.publish_catalog_update.await_args
    assert awaited_call is not None
    request = awaited_call.args[0]
    assert request.action_id == str(action_id)
    assert request.draft_id == str(action_id)
    assert request.sku == "NOVA-AUDIO-001"
    assert request.expected_catalog_version == 1
    assert update == {
        "catalog_execution_result": execution,
        "catalog_error": None,
        "error": None,
    }


@pytest.mark.asyncio
@patch("commercepilot.graph.orchestrator_graph.CommercePilotMCPClient")
@patch("commercepilot.graph.orchestrator_graph.SessionLocal")
async def test_execute_campaign_launch_calls_mcp_with_approved_snapshot(
    session_factory: MagicMock,
    client_factory: MagicMock,
) -> None:
    state = initial_state()
    action_id = uuid4()
    state["campaign_launch_action_id"] = action_id
    action = MagicMock()
    action.id = action_id
    action.action_type = "launch_campaign"
    action.idempotency_key = f"campaign-launch:{action_id}"
    action.payload = {
        "draft_id": str(action_id),
        "product_sku": "NOVA-AUDIO-001",
        "source_catalog_version": 3,
        "source_price": "99.99",
    }
    session_factory.return_value.__enter__.return_value.get.return_value = action
    execution = LaunchCampaignResult(
        status="executed",
        action_id=str(action_id),
        draft_id=str(action_id),
        sku="NOVA-AUDIO-001",
        launched_at="2026-11-20T12:00:00Z",
        replayed=False,
    )
    client = client_factory.return_value
    client.launch_campaign = AsyncMock(return_value=execution)

    update = await execute_campaign_launch_node(state)

    awaited_call = client.launch_campaign.await_args
    assert awaited_call is not None
    request = awaited_call.args[0]
    assert request.action_id == str(action_id)
    assert request.draft_id == str(action_id)
    assert request.sku == "NOVA-AUDIO-001"
    assert request.source_catalog_version == 3
    assert request.source_price == "99.99"
    assert update == {
        "campaign_execution_result": execution,
        "campaign_error": None,
        "error": None,
    }
