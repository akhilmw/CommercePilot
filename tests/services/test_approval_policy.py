from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.enums import (
    ActionType,
    ImprovementPriority,
    SourceAgent,
)
from commercepilot.models.orchestration import ActionProposal
from commercepilot.services.approval_policy import (
    APPROVAL_REQUIRED_ACTIONS,
    NO_APPROVAL_REQUIRED_ACTIONS,
    apply_approval_policy,
    requires_human_approval,
)


def make_proposal(action_type: ActionType) -> ActionProposal:
    return ActionProposal(
        action_type=action_type,
        title="Respond to current market evidence",
        description="Prepare an appropriate response to the observed evidence.",
        rationale="The available evidence indicates that a response is warranted.",
        priority=ImprovementPriority.HIGH,
        source_agents=[SourceAgent.ORCHESTRATOR],
        evidence_ids=[uuid4()],
    )


def test_every_action_type_has_exactly_one_policy() -> None:
    assert APPROVAL_REQUIRED_ACTIONS.isdisjoint(NO_APPROVAL_REQUIRED_ACTIONS)
    assert set(ActionType) == (
        APPROVAL_REQUIRED_ACTIONS | NO_APPROVAL_REQUIRED_ACTIONS
    )


@pytest.mark.parametrize(
    "action_type",
    sorted(APPROVAL_REQUIRED_ACTIONS, key=str),
)
def test_mutating_actions_require_approval(action_type: ActionType) -> None:
    assert requires_human_approval(action_type) is True


@pytest.mark.parametrize(
    "action_type",
    sorted(NO_APPROVAL_REQUIRED_ACTIONS, key=str),
)
def test_read_and_draft_actions_do_not_require_approval(
    action_type: ActionType,
) -> None:
    assert requires_human_approval(action_type) is False


def test_apply_approval_policy_marks_mixed_action_set() -> None:
    result = apply_approval_policy(
        [
            make_proposal(ActionType.DRAFT_CAMPAIGN),
            make_proposal(ActionType.LAUNCH_CAMPAIGN),
        ]
    )

    assert result.requires_human_approval is True
    assert result.actions[0].requires_human_approval is False
    assert result.actions[1].requires_human_approval is True


def test_action_proposal_rejects_llm_supplied_approval_field() -> None:
    proposal = make_proposal(ActionType.CHANGE_PRICE).model_dump()
    proposal["requires_human_approval"] = False

    with pytest.raises(ValidationError):
        ActionProposal.model_validate(proposal)
