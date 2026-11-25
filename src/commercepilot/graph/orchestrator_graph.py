from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from commercepilot.core.config import get_settings
from commercepilot.db.models import ApprovedAction, Product
from commercepilot.db.session import SessionLocal
from commercepilot.graph.campaign_graph import build_campaign_graph
from commercepilot.graph.campaign_state import CampaignAgentState
from commercepilot.graph.catalog_graph import build_catalog_graph
from commercepilot.graph.catalog_state import CatalogAgentState
from commercepilot.graph.competitor_graph import build_competitor_graph
from commercepilot.graph.competitor_state import CompetitorAgentState
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.graph.review_graph import build_review_graph
from commercepilot.graph.review_state import ReviewAgentState
from commercepilot.graph.stage_observability import StageObserver, observe_stage
from commercepilot.mcp.client import (
    CommercePilotMCPClient,
    LaunchCampaignRequest,
    LaunchCampaignResult,
    PublishCatalogUpdateRequest,
    PublishCatalogUpdateResult,
    UpdateProductPriceRequest,
    UpdateProductPriceResult,
)
from commercepilot.models.campaign import CampaignLaunchPreview
from commercepilot.models.catalog import CatalogComparison
from commercepilot.models.enums import ActionType
from commercepilot.models.orchestration import HumanApprovalDecision
from commercepilot.models.product import ProductRead
from commercepilot.services.approval_policy import apply_approval_policy
from commercepilot.services.approved_actions import persist_approved_price_actions
from commercepilot.services.campaign_approval import process_campaign_approval
from commercepilot.services.campaign_persistence import save_campaign_draft
from commercepilot.services.campaign_preview import build_campaign_launch_preview
from commercepilot.services.catalog_approval import process_catalog_approval
from commercepilot.services.catalog_comparison import build_catalog_comparison
from commercepilot.services.catalog_persistence import save_catalog_draft
from commercepilot.services.strategy_synthesis import synthesize_strategy

RUN_REVIEW_AGENT_NODE = "run_review_agent"
RUN_COMPETITOR_AGENT_NODE = "run_competitor_agent"
SYNTHESIZE_STRATEGY_NODE = "synthesize_strategy"
RUN_CATALOG_AGENT_NODE = "run_catalog_agent"
PERSIST_CATALOG_DRAFT_NODE = "persist_catalog_draft"
BUILD_CATALOG_COMPARISON_NODE = "build_catalog_comparison"
REQUEST_CATALOG_APPROVAL_NODE = "request_catalog_approval"
PROCESS_CATALOG_APPROVAL_NODE = "process_catalog_approval"
EXECUTE_CATALOG_PUBLISH_NODE = "execute_catalog_publish"
RUN_CAMPAIGN_AGENT_NODE = "run_campaign_agent"
PERSIST_CAMPAIGN_DRAFT_NODE = "persist_campaign_draft"
BUILD_CAMPAIGN_PREVIEW_NODE = "build_campaign_preview"
REQUEST_CAMPAIGN_APPROVAL_NODE = "request_campaign_approval"
PROCESS_CAMPAIGN_APPROVAL_NODE = "process_campaign_approval"
EXECUTE_CAMPAIGN_LAUNCH_NODE = "execute_campaign_launch"
APPLY_APPROVAL_POLICY_NODE = "apply_approval_policy"
REQUEST_HUMAN_APPROVAL_NODE = "request_human_approval"
PERSIST_APPROVED_ACTIONS_NODE = "persist_approved_actions"
EXECUTE_APPROVED_ACTIONS_NODE = "execute_approved_actions"


def run_review_agent_node(state: CommercePilotState) -> dict[str, Any]:
    graph = build_review_graph()
    result = graph.invoke(
        ReviewAgentState(
            product_sku=state["product_sku"],
            evidence=None,
            insight=None,
            error=None,
        )
    )
    return {
        "review_insight": result["insight"],
        "review_error": result["error"],
    }


def run_competitor_agent_node(state: CommercePilotState) -> dict[str, Any]:
    graph = build_competitor_graph()
    result = graph.invoke(
        CompetitorAgentState(
            product_sku=state["product_sku"],
            evidence=None,
            insight=None,
            error=None,
        )
    )
    return {
        "competitor_insight": result["insight"],
        "competitor_error": result["error"],
    }


def synthesize_strategy_node(state: CommercePilotState) -> dict[str, Any]:
    if state["review_error"] is not None:
        return {"strategy": None, "error": state["review_error"]}
    if state["competitor_error"] is not None:
        return {"strategy": None, "error": state["competitor_error"]}

    review_insight = state["review_insight"]
    competitor_insight = state["competitor_insight"]
    if review_insight is None or competitor_insight is None:
        return {
            "strategy": None,
            "error": "Both specialized agent insights are required.",
        }

    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "strategy": None,
            "error": "COMMERCEPILOT_OPENAI_API_KEY is not configured.",
        }

    try:
        strategy = synthesize_strategy(
            review_insight,
            competitor_insight,
            client=OpenAI(api_key=settings.openai_api_key),
            model=settings.openai_model,
        )
        next_state: CommercePilotState = {**state, "strategy": strategy}
        requires_catalog_publish = False
        if _should_run_campaign(next_state):
            with SessionLocal() as session:
                product = session.scalar(
                    select(Product).where(Product.sku == state["product_sku"])
                )
                if product is None:
                    raise ValueError(f"Unknown product SKU: {state['product_sku']}")
                requires_catalog_publish = not ProductRead.model_validate(
                    product
                ).has_published_catalog
    except (OpenAIError, SQLAlchemyError, ValueError) as error:
        return {"strategy": None, "error": str(error)}

    return {
        "strategy": strategy,
        "campaign_requires_catalog_publish": requires_catalog_publish,
        "error": None,
    }


def run_catalog_agent_node(state: CommercePilotState) -> dict[str, Any]:
    review_insight = state["review_insight"]
    competitor_insight = state["competitor_insight"]
    if review_insight is None or competitor_insight is None:
        error = "Both agent insights are required for catalog generation."
        return {
            "catalog_draft": None,
            "catalog_error": error,
            "error": error,
        }

    graph = build_catalog_graph()
    result = graph.invoke(
        CatalogAgentState(
            product_sku=state["product_sku"],
            review_insight=review_insight,
            competitor_insight=competitor_insight,
            evidence=None,
            draft=None,
            error=None,
        )
    )
    return {
        "catalog_draft": result["draft"],
        "catalog_error": result["error"],
        "error": result["error"],
    }


def persist_catalog_draft_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    draft = state["catalog_draft"]
    if draft is None:
        error = "A validated catalog draft is required before persistence."
        return {
            "catalog_draft_id": None,
            "catalog_error": error,
            "error": error,
        }

    try:
        with SessionLocal() as session:
            record = save_catalog_draft(session, draft)
            draft_id = record.id
    except (SQLAlchemyError, ValueError) as error:
        return {
            "catalog_draft_id": None,
            "catalog_error": str(error),
            "error": str(error),
        }

    return {
        "catalog_draft_id": draft_id,
        "catalog_error": None,
        "error": None,
    }


def build_catalog_comparison_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    draft_id = state["catalog_draft_id"]
    if draft_id is None:
        error = "A saved catalog draft is required before comparison."
        return {
            "catalog_comparison": None,
            "catalog_error": error,
            "error": error,
        }

    try:
        with SessionLocal() as session:
            comparison = build_catalog_comparison(session, draft_id)
    except (SQLAlchemyError, ValueError) as error:
        return {
            "catalog_comparison": None,
            "catalog_error": str(error),
            "error": str(error),
        }

    return {
        "catalog_comparison": comparison,
        "catalog_error": None,
        "error": None,
    }


def request_catalog_approval_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    comparison = state["catalog_comparison"]
    if comparison is None:
        error = "A catalog comparison is required before approval."
        return {
            "catalog_approval_decision": None,
            "catalog_error": error,
            "error": error,
        }
    comparison = CatalogComparison.model_validate(comparison.__dict__)
    if comparison.is_stale:
        error = (
            "Catalog draft is stale: expected version "
            f"{comparison.expected_catalog_version}, current version "
            f"{comparison.current_catalog_version}."
        )
        return {
            "catalog_approval_decision": None,
            "catalog_error": error,
            "error": error,
        }

    decision = interrupt(
        {
            "type": "catalog_publish_approval_required",
            "product_sku": comparison.product_sku,
            "draft_id": str(comparison.draft_id),
            "comparison": comparison.model_dump(mode="json"),
        }
    )
    return {
        "catalog_comparison": comparison,
        "catalog_approval_decision": (HumanApprovalDecision.model_validate(decision)),
        "catalog_error": None,
        "error": None,
    }


def process_catalog_approval_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    draft_id = state["catalog_draft_id"]
    decision = state["catalog_approval_decision"]
    if draft_id is None or decision is None:
        error = "Catalog draft and approval decision are required."
        return {
            "catalog_publish_action_id": None,
            "catalog_error": error,
            "error": error,
        }

    try:
        with SessionLocal() as session:
            action = process_catalog_approval(
                session,
                draft_id,
                decision,
            )
            action_id = action.id if action is not None else None
    except (SQLAlchemyError, ValueError) as error:
        return {
            "catalog_publish_action_id": None,
            "catalog_error": str(error),
            "error": str(error),
        }

    update = {
        "catalog_publish_action_id": action_id,
        "catalog_error": None,
        "error": None,
    }
    if not decision.approved and state.get("campaign_requires_catalog_publish"):
        return {
            **update,
            "campaign_skip_reason": (
                "Campaign skipped because catalog publishing was declined."
            ),
        }
    return update


async def execute_catalog_publish_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    action_id = state["catalog_publish_action_id"]
    if action_id is None:
        return {
            "catalog_execution_result": None,
            "catalog_error": None,
            "error": None,
        }

    with SessionLocal() as session:
        action = session.get(ApprovedAction, action_id)
        if action is None:
            error = f"Approved catalog action not found: {action_id}"
            return {
                "catalog_execution_result": None,
                "catalog_error": error,
                "error": error,
            }
        if action.action_type != "publish_catalog_update":
            error = f"Unexpected catalog action type: {action.action_type}"
            return {
                "catalog_execution_result": None,
                "catalog_error": error,
                "error": error,
            }
        payload = action.payload
        request = PublishCatalogUpdateRequest(
            action_id=str(action.id),
            idempotency_key=action.idempotency_key,
            draft_id=str(payload["draft_id"]),
            sku=str(payload["product_sku"]),
            expected_catalog_version=int(payload["expected_catalog_version"]),
        )

    client = CommercePilotMCPClient(get_settings().mcp_base_url)
    try:
        result: PublishCatalogUpdateResult = await client.publish_catalog_update(
            request
        )
    except RuntimeError as error:
        return {
            "catalog_execution_result": None,
            "catalog_error": str(error),
            "error": str(error),
        }

    return {
        "catalog_execution_result": result,
        "catalog_error": None,
        "error": None,
    }


def run_campaign_agent_node(state: CommercePilotState) -> dict[str, Any]:
    review_insight = state["review_insight"]
    competitor_insight = state["competitor_insight"]
    strategy = state["strategy"]
    if review_insight is None or competitor_insight is None or strategy is None:
        error = "Review, competitor, and strategy inputs are required."
        return {
            "campaign_evidence": None,
            "campaign_draft": None,
            "campaign_error": error,
            "error": error,
        }

    graph = build_campaign_graph()
    result = graph.invoke(
        CampaignAgentState(
            product_sku=state["product_sku"],
            review_insight=review_insight,
            competitor_insight=competitor_insight,
            strategy=strategy,
            evidence=None,
            draft=None,
            error=None,
        )
    )
    return {
        "campaign_evidence": result["evidence"],
        "campaign_draft": result["draft"],
        "campaign_error": result["error"],
        "error": result["error"],
    }


def persist_campaign_draft_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    draft = state["campaign_draft"]
    evidence = state["campaign_evidence"]
    if draft is None or evidence is None:
        error = "A validated campaign draft and evidence are required."
        return {
            "campaign_draft_id": None,
            "campaign_error": error,
            "error": error,
        }

    try:
        with SessionLocal() as session:
            record = save_campaign_draft(session, draft, evidence)
            draft_id = record.id
    except (SQLAlchemyError, ValueError) as error:
        return {
            "campaign_draft_id": None,
            "campaign_error": str(error),
            "error": str(error),
        }
    return {
        "campaign_draft_id": draft_id,
        "campaign_error": None,
        "error": None,
    }


def build_campaign_preview_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    draft_id = state["campaign_draft_id"]
    if draft_id is None:
        error = "A saved campaign draft is required before preview."
        return {
            "campaign_preview": None,
            "campaign_error": error,
            "error": error,
        }
    try:
        with SessionLocal() as session:
            preview = build_campaign_launch_preview(session, draft_id)
    except (SQLAlchemyError, ValueError) as error:
        return {
            "campaign_preview": None,
            "campaign_error": str(error),
            "error": str(error),
        }
    return {
        "campaign_preview": preview,
        "campaign_error": None,
        "error": None,
    }


def request_campaign_approval_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    preview = state["campaign_preview"]
    if preview is None:
        error = "A campaign launch preview is required before approval."
        return {
            "campaign_approval_decision": None,
            "campaign_error": error,
            "error": error,
        }
    preview = CampaignLaunchPreview.model_validate(preview.__dict__)
    if preview.is_stale:
        error = "Campaign draft is stale because catalog or price changed."
        return {
            "campaign_approval_decision": None,
            "campaign_error": error,
            "error": error,
        }

    decision = interrupt(
        {
            "type": "campaign_launch_approval_required",
            "product_sku": preview.product_sku,
            "draft_id": str(preview.draft_id),
            "preview": preview.model_dump(mode="json"),
        }
    )
    return {
        "campaign_preview": preview,
        "campaign_approval_decision": (HumanApprovalDecision.model_validate(decision)),
        "campaign_error": None,
        "error": None,
    }


def process_campaign_approval_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    draft_id = state["campaign_draft_id"]
    decision = state["campaign_approval_decision"]
    if draft_id is None or decision is None:
        error = "Campaign draft and approval decision are required."
        return {
            "campaign_launch_action_id": None,
            "campaign_error": error,
            "error": error,
        }
    try:
        with SessionLocal() as session:
            action = process_campaign_approval(session, draft_id, decision)
            action_id = action.id if action is not None else None
    except (SQLAlchemyError, ValueError) as error:
        return {
            "campaign_launch_action_id": None,
            "campaign_error": str(error),
            "error": str(error),
        }
    return {
        "campaign_launch_action_id": action_id,
        "campaign_error": None,
        "error": None,
    }


async def execute_campaign_launch_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    action_id = state["campaign_launch_action_id"]
    if action_id is None:
        return {
            "campaign_execution_result": None,
            "campaign_error": None,
            "error": None,
        }

    with SessionLocal() as session:
        action = session.get(ApprovedAction, action_id)
        if action is None:
            error = f"Approved campaign action not found: {action_id}"
            return {
                "campaign_execution_result": None,
                "campaign_error": error,
                "error": error,
            }
        if action.action_type != "launch_campaign":
            error = f"Unexpected campaign action type: {action.action_type}"
            return {
                "campaign_execution_result": None,
                "campaign_error": error,
                "error": error,
            }
        payload = action.payload
        request = LaunchCampaignRequest(
            action_id=str(action.id),
            idempotency_key=action.idempotency_key,
            draft_id=str(payload["draft_id"]),
            sku=str(payload["product_sku"]),
            source_catalog_version=int(payload["source_catalog_version"]),
            source_price=str(payload["source_price"]),
        )

    client = CommercePilotMCPClient(get_settings().mcp_base_url)
    try:
        result: LaunchCampaignResult = await client.launch_campaign(request)
    except RuntimeError as error:
        return {
            "campaign_execution_result": None,
            "campaign_error": str(error),
            "error": str(error),
        }
    return {
        "campaign_execution_result": result,
        "campaign_error": None,
        "error": None,
    }


def apply_approval_policy_node(state: CommercePilotState) -> dict[str, Any]:
    strategy = state["strategy"]
    if strategy is None:
        return {
            "approval_policy": None,
            "error": "A strategy is required before applying approval policy.",
        }

    return {
        "approval_policy": apply_approval_policy(strategy.action_proposals),
        "error": None,
    }


def request_human_approval_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    policy = state["approval_policy"]
    if policy is None:
        return {
            "approval_decision": None,
            "error": "Approval policy is required before requesting approval.",
        }

    pending_actions = [
        action.model_dump(mode="json")
        for action in policy.actions
        if action.requires_human_approval
    ]
    decision = interrupt(
        {
            "type": "human_approval_required",
            "product_sku": state["product_sku"],
            "actions": pending_actions,
        }
    )

    return {
        "approval_decision": HumanApprovalDecision.model_validate(decision),
        "error": None,
    }


def persist_approved_actions_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    decision = state["approval_decision"]
    policy = state["approval_policy"]
    if decision is None or policy is None:
        return {
            "approved_action_ids": [],
            "error": "Approval state is incomplete.",
        }
    if not decision.approved:
        return {"approved_action_ids": [], "error": None}

    try:
        with SessionLocal() as session:
            actions = persist_approved_price_actions(
                session,
                policy,
                decision,
            )
            action_ids = [action.id for action in actions]
    except ValueError as error:
        return {"approved_action_ids": [], "error": str(error)}

    return {"approved_action_ids": action_ids, "error": None}


async def execute_approved_actions_node(
    state: CommercePilotState,
) -> dict[str, Any]:
    if not state["approved_action_ids"]:
        return {"execution_results": [], "error": None}

    requests: list[UpdateProductPriceRequest] = []
    with SessionLocal() as session:
        for action_id in state["approved_action_ids"]:
            action = session.get(ApprovedAction, action_id)
            if action is None:
                return {
                    "execution_results": [],
                    "error": f"Approved action not found: {action_id}",
                }
            payload = action.payload
            requests.append(
                UpdateProductPriceRequest(
                    action_id=str(action.id),
                    idempotency_key=action.idempotency_key,
                    sku=str(payload["sku"]),
                    expected_current_price=str(payload["expected_current_price"]),
                    new_price=str(payload["new_price"]),
                )
            )

    client = CommercePilotMCPClient(get_settings().mcp_base_url)
    results: list[UpdateProductPriceResult] = []
    for request in requests:
        try:
            result = await client.update_product_price(request)
        except RuntimeError as error:
            return {"execution_results": results, "error": str(error)}
        results.append(result)

    return {"execution_results": results, "error": None}


def route_after_synthesis(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    strategy = state["strategy"]
    if strategy is None:
        return END
    if state["force_catalog_update"] or any(
        action.action_type is ActionType.DRAFT_CATALOG_UPDATE
        for action in strategy.action_proposals
    ):
        return RUN_CATALOG_AGENT_NODE
    if _should_run_campaign(state):
        if state.get("campaign_requires_catalog_publish"):
            return RUN_CATALOG_AGENT_NODE
        return RUN_CAMPAIGN_AGENT_NODE
    return APPLY_APPROVAL_POLICY_NODE


def _should_run_campaign(state: CommercePilotState) -> bool:
    strategy = state["strategy"]
    return state["force_campaign_update"] or (
        strategy is not None
        and any(
            action.action_type is ActionType.DRAFT_CAMPAIGN
            for action in strategy.action_proposals
        )
    )


def route_after_catalog_agent(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return PERSIST_CATALOG_DRAFT_NODE


def route_after_catalog_persistence(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return BUILD_CATALOG_COMPARISON_NODE


def route_after_catalog_comparison(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return REQUEST_CATALOG_APPROVAL_NODE


def route_after_catalog_approval(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return PROCESS_CATALOG_APPROVAL_NODE


def route_after_processing_catalog_approval(
    state: CommercePilotState,
) -> str:
    if state["error"] is not None:
        return END
    if state["catalog_publish_action_id"] is not None:
        return EXECUTE_CATALOG_PUBLISH_NODE
    if _should_run_campaign(state) and not state.get(
        "campaign_requires_catalog_publish"
    ):
        return RUN_CAMPAIGN_AGENT_NODE
    return APPLY_APPROVAL_POLICY_NODE


def route_after_catalog_execution(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    if _should_run_campaign(state):
        return RUN_CAMPAIGN_AGENT_NODE
    return APPLY_APPROVAL_POLICY_NODE


def route_after_campaign_agent(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return PERSIST_CAMPAIGN_DRAFT_NODE


def route_after_campaign_persistence(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return BUILD_CAMPAIGN_PREVIEW_NODE


def route_after_campaign_preview(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return REQUEST_CAMPAIGN_APPROVAL_NODE


def route_after_campaign_approval(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return PROCESS_CAMPAIGN_APPROVAL_NODE


def route_after_processing_campaign_approval(
    state: CommercePilotState,
) -> str:
    if state["error"] is not None:
        return END
    if state["campaign_launch_action_id"] is not None:
        return EXECUTE_CAMPAIGN_LAUNCH_NODE
    return APPLY_APPROVAL_POLICY_NODE


def route_after_campaign_execution(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return APPLY_APPROVAL_POLICY_NODE


def route_after_approval_policy(state: CommercePilotState) -> str:
    policy = state["approval_policy"]
    if state["error"] is not None or policy is None:
        return END
    if policy.requires_human_approval:
        return REQUEST_HUMAN_APPROVAL_NODE
    return END


def route_after_human_decision(state: CommercePilotState) -> str:
    decision = state["approval_decision"]
    if state["error"] is not None or decision is None or not decision.approved:
        return END
    return PERSIST_APPROVED_ACTIONS_NODE


def route_after_persisting_actions(state: CommercePilotState) -> str:
    if state["error"] is not None:
        return END
    return EXECUTE_APPROVED_ACTIONS_NODE


def build_orchestrator_graph(
    checkpointer: Any | None = None,
    *,
    stage_observer: StageObserver | None = None,
) -> Any:
    graph = StateGraph(CommercePilotState)
    for name, node, title in (
        (RUN_REVIEW_AGENT_NODE, run_review_agent_node, "Review analysis"),
        (RUN_COMPETITOR_AGENT_NODE, run_competitor_agent_node, "Competitor analysis"),
        (SYNTHESIZE_STRATEGY_NODE, synthesize_strategy_node, "Strategy synthesis"),
        (RUN_CATALOG_AGENT_NODE, run_catalog_agent_node, "Catalog generation"),
        (RUN_CAMPAIGN_AGENT_NODE, run_campaign_agent_node, "Campaign generation"),
    ):
        graph.add_node(name, observe_stage(node, title, stage_observer))
    graph.add_node(
        PERSIST_CATALOG_DRAFT_NODE,
        persist_catalog_draft_node,
    )
    graph.add_node(
        BUILD_CATALOG_COMPARISON_NODE,
        build_catalog_comparison_node,
    )
    graph.add_node(
        REQUEST_CATALOG_APPROVAL_NODE,
        request_catalog_approval_node,
    )
    graph.add_node(
        PROCESS_CATALOG_APPROVAL_NODE,
        process_catalog_approval_node,
    )
    graph.add_node(
        EXECUTE_CATALOG_PUBLISH_NODE,
        execute_catalog_publish_node,
    )
    graph.add_node(PERSIST_CAMPAIGN_DRAFT_NODE, persist_campaign_draft_node)
    graph.add_node(BUILD_CAMPAIGN_PREVIEW_NODE, build_campaign_preview_node)
    graph.add_node(REQUEST_CAMPAIGN_APPROVAL_NODE, request_campaign_approval_node)
    graph.add_node(PROCESS_CAMPAIGN_APPROVAL_NODE, process_campaign_approval_node)
    graph.add_node(EXECUTE_CAMPAIGN_LAUNCH_NODE, execute_campaign_launch_node)
    graph.add_node(
        APPLY_APPROVAL_POLICY_NODE,
        apply_approval_policy_node,
    )
    graph.add_node(
        REQUEST_HUMAN_APPROVAL_NODE,
        request_human_approval_node,
    )
    graph.add_node(
        PERSIST_APPROVED_ACTIONS_NODE,
        persist_approved_actions_node,
    )
    graph.add_node(
        EXECUTE_APPROVED_ACTIONS_NODE,
        execute_approved_actions_node,
    )

    graph.add_edge(START, RUN_REVIEW_AGENT_NODE)
    graph.add_edge(START, RUN_COMPETITOR_AGENT_NODE)
    graph.add_edge(
        [RUN_REVIEW_AGENT_NODE, RUN_COMPETITOR_AGENT_NODE],
        SYNTHESIZE_STRATEGY_NODE,
    )
    graph.add_conditional_edges(
        SYNTHESIZE_STRATEGY_NODE,
        route_after_synthesis,
        {
            RUN_CATALOG_AGENT_NODE: RUN_CATALOG_AGENT_NODE,
            RUN_CAMPAIGN_AGENT_NODE: RUN_CAMPAIGN_AGENT_NODE,
            APPLY_APPROVAL_POLICY_NODE: APPLY_APPROVAL_POLICY_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        RUN_CATALOG_AGENT_NODE,
        route_after_catalog_agent,
        {
            PERSIST_CATALOG_DRAFT_NODE: PERSIST_CATALOG_DRAFT_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        PERSIST_CATALOG_DRAFT_NODE,
        route_after_catalog_persistence,
        {
            BUILD_CATALOG_COMPARISON_NODE: BUILD_CATALOG_COMPARISON_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        BUILD_CATALOG_COMPARISON_NODE,
        route_after_catalog_comparison,
        {
            REQUEST_CATALOG_APPROVAL_NODE: REQUEST_CATALOG_APPROVAL_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        REQUEST_CATALOG_APPROVAL_NODE,
        route_after_catalog_approval,
        {
            PROCESS_CATALOG_APPROVAL_NODE: PROCESS_CATALOG_APPROVAL_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        PROCESS_CATALOG_APPROVAL_NODE,
        route_after_processing_catalog_approval,
        {
            EXECUTE_CATALOG_PUBLISH_NODE: EXECUTE_CATALOG_PUBLISH_NODE,
            RUN_CAMPAIGN_AGENT_NODE: RUN_CAMPAIGN_AGENT_NODE,
            APPLY_APPROVAL_POLICY_NODE: APPLY_APPROVAL_POLICY_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        EXECUTE_CATALOG_PUBLISH_NODE,
        route_after_catalog_execution,
        {
            RUN_CAMPAIGN_AGENT_NODE: RUN_CAMPAIGN_AGENT_NODE,
            APPLY_APPROVAL_POLICY_NODE: APPLY_APPROVAL_POLICY_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        RUN_CAMPAIGN_AGENT_NODE,
        route_after_campaign_agent,
        {PERSIST_CAMPAIGN_DRAFT_NODE: PERSIST_CAMPAIGN_DRAFT_NODE, END: END},
    )
    graph.add_conditional_edges(
        PERSIST_CAMPAIGN_DRAFT_NODE,
        route_after_campaign_persistence,
        {BUILD_CAMPAIGN_PREVIEW_NODE: BUILD_CAMPAIGN_PREVIEW_NODE, END: END},
    )
    graph.add_conditional_edges(
        BUILD_CAMPAIGN_PREVIEW_NODE,
        route_after_campaign_preview,
        {REQUEST_CAMPAIGN_APPROVAL_NODE: REQUEST_CAMPAIGN_APPROVAL_NODE, END: END},
    )
    graph.add_conditional_edges(
        REQUEST_CAMPAIGN_APPROVAL_NODE,
        route_after_campaign_approval,
        {PROCESS_CAMPAIGN_APPROVAL_NODE: PROCESS_CAMPAIGN_APPROVAL_NODE, END: END},
    )
    graph.add_conditional_edges(
        PROCESS_CAMPAIGN_APPROVAL_NODE,
        route_after_processing_campaign_approval,
        {
            EXECUTE_CAMPAIGN_LAUNCH_NODE: EXECUTE_CAMPAIGN_LAUNCH_NODE,
            APPLY_APPROVAL_POLICY_NODE: APPLY_APPROVAL_POLICY_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        EXECUTE_CAMPAIGN_LAUNCH_NODE,
        route_after_campaign_execution,
        {APPLY_APPROVAL_POLICY_NODE: APPLY_APPROVAL_POLICY_NODE, END: END},
    )
    graph.add_conditional_edges(
        APPLY_APPROVAL_POLICY_NODE,
        route_after_approval_policy,
        {
            REQUEST_HUMAN_APPROVAL_NODE: REQUEST_HUMAN_APPROVAL_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        REQUEST_HUMAN_APPROVAL_NODE,
        route_after_human_decision,
        {
            PERSIST_APPROVED_ACTIONS_NODE: PERSIST_APPROVED_ACTIONS_NODE,
            END: END,
        },
    )
    graph.add_conditional_edges(
        PERSIST_APPROVED_ACTIONS_NODE,
        route_after_persisting_actions,
        {
            EXECUTE_APPROVED_ACTIONS_NODE: EXECUTE_APPROVED_ACTIONS_NODE,
            END: END,
        },
    )
    graph.add_edge(EXECUTE_APPROVED_ACTIONS_NODE, END)
    return graph.compile(checkpointer=checkpointer)
