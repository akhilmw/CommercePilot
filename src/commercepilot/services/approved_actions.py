from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovedAction
from commercepilot.models.enums import ActionType
from commercepilot.models.orchestration import (
    ApprovalPolicyResult,
    HumanApprovalDecision,
)


def persist_approved_price_actions(
    session: Session,
    policy: ApprovalPolicyResult,
    decision: HumanApprovalDecision,
) -> Sequence[ApprovedAction]:
    if not decision.approved:
        return []

    unsupported = [
        action.action_type
        for action in policy.actions
        if action.requires_human_approval
        and action.action_type is not ActionType.CHANGE_PRICE
    ]
    if unsupported:
        names = ", ".join(action_type.value for action_type in unsupported)
        raise ValueError(f"No MCP executor exists for approved actions: {names}")

    records: list[ApprovedAction] = []
    for action in policy.actions:
        if action.action_type is not ActionType.CHANGE_PRICE:
            continue

        parameters = action.price_change
        if parameters is None:
            raise ValueError("Approved price action has no parameters.")

        payload = parameters.model_dump(mode="json")
        idempotency_key = f"price-change:{action.action_id}"
        existing = session.get(ApprovedAction, action.action_id)
        if existing is not None:
            if (
                existing.action_type != action.action_type.value
                or existing.idempotency_key != idempotency_key
                or existing.payload != payload
            ):
                raise ValueError(
                    f"Existing approved action does not match: {action.action_id}"
                )
            records.append(existing)
            continue

        record = ApprovedAction(
            id=action.action_id,
            action_type=action.action_type.value,
            idempotency_key=idempotency_key,
            payload=payload,
            status="approved",
            approved_by=decision.reviewer,
            approved_at=datetime.now(UTC),
        )
        session.add(record)
        records.append(record)

    session.commit()
    return records
