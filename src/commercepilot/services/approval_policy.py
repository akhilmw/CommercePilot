from collections.abc import Sequence

from commercepilot.models.enums import ActionType
from commercepilot.models.orchestration import (
    ActionProposal,
    ApprovalPolicyResult,
    GovernedAction,
)

APPROVAL_REQUIRED_ACTIONS = frozenset(
    {
        ActionType.PUBLISH_CATALOG_UPDATE,
        ActionType.LAUNCH_CAMPAIGN,
        ActionType.CHANGE_PRICE,
    }
)

NO_APPROVAL_REQUIRED_ACTIONS = frozenset(
    {
        ActionType.ANALYZE_REVIEWS,
        ActionType.MONITOR_COMPETITORS,
        ActionType.RECOMMEND_PRODUCT_IMPROVEMENT,
        ActionType.DRAFT_CATALOG_UPDATE,
        ActionType.DRAFT_CAMPAIGN,
    }
)


def requires_human_approval(action_type: ActionType) -> bool:
    if action_type in APPROVAL_REQUIRED_ACTIONS:
        return True
    if action_type in NO_APPROVAL_REQUIRED_ACTIONS:
        return False

    raise ValueError(f"No approval policy exists for action: {action_type}")


def apply_approval_policy(
    proposals: Sequence[ActionProposal],
) -> ApprovalPolicyResult:
    governed_actions = [
        GovernedAction(
            **proposal.model_dump(),
            requires_human_approval=requires_human_approval(
                proposal.action_type
            ),
        )
        for proposal in proposals
    ]

    return ApprovalPolicyResult(
        actions=governed_actions,
        requires_human_approval=any(
            action.requires_human_approval for action in governed_actions
        ),
    )
