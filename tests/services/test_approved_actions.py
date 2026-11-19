from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovedAction
from commercepilot.models.enums import (
    ActionType,
    ImprovementPriority,
    SourceAgent,
)
from commercepilot.models.orchestration import (
    ActionProposal,
    HumanApprovalDecision,
    PriceChangeParameters,
)
from commercepilot.services.approval_policy import apply_approval_policy
from commercepilot.services.approved_actions import (
    persist_approved_price_actions,
)


def make_policy():
    proposal = ActionProposal(
        action_type=ActionType.CHANGE_PRICE,
        title="Run a temporary promotional price",
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
    return apply_approval_policy([proposal])


def test_persist_approved_price_action() -> None:
    session = MagicMock(spec=Session)
    session.get.return_value = None
    decision = HumanApprovalDecision(
        approved=True,
        reviewer="test-user",
    )

    records = persist_approved_price_actions(
        session,
        make_policy(),
        decision,
    )

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, ApprovedAction)
    assert record.action_type == "change_price"
    assert record.payload == {
        "sku": "NOVA-AUDIO-001",
        "expected_current_price": "129.99",
        "new_price": "119.99",
        "currency": "USD",
    }
    assert record.idempotency_key == f"price-change:{record.id}"
    session.add.assert_called_once_with(record)
    session.commit.assert_called_once()


def test_rejected_decision_creates_no_approval() -> None:
    session = MagicMock(spec=Session)
    decision = HumanApprovalDecision(
        approved=False,
        reviewer="test-user",
    )

    records = persist_approved_price_actions(
        session,
        make_policy(),
        decision,
    )

    assert records == []
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_existing_mismatched_approval_is_rejected() -> None:
    session = MagicMock(spec=Session)
    existing = MagicMock(spec=ApprovedAction)
    existing.action_type = "change_price"
    existing.idempotency_key = "wrong-key"
    existing.payload = {}
    session.get.return_value = existing

    with pytest.raises(ValueError, match="does not match"):
        persist_approved_price_actions(
            session,
            make_policy(),
            HumanApprovalDecision(approved=True, reviewer="test-user"),
        )
