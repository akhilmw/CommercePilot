from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.models.orchestration_api import (
    ApprovalDecisionRequest,
    ApprovalRequestRead,
    OrchestrationRunCreate,
    OrchestrationRunRead,
)


def test_orchestration_run_create_defaults_to_normal_routing() -> None:
    request = OrchestrationRunCreate(product_sku="NOVA-AUDIO-001")

    assert request.force_catalog_update is False
    assert request.force_campaign_update is False


def test_orchestration_run_create_rejects_invalid_sku() -> None:
    with pytest.raises(ValidationError):
        OrchestrationRunCreate(product_sku="nova sound")


def test_approval_decision_requires_reviewer() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecisionRequest(approved=True, reviewer="")


def test_api_read_models_accept_database_attributes() -> None:
    now = datetime.now(UTC)
    run_id = uuid4()
    product_id = uuid4()
    run = OrchestrationRunRead(
        id=run_id,
        thread_id=uuid4(),
        product_id=product_id,
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        status=OrchestrationRunStatus.AWAITING_APPROVAL,
        current_stage="campaign_launch_approval_required",
        force_catalog_update=False,
        force_campaign_update=True,
        result=None,
        error=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    approval = ApprovalRequestRead(
        id=uuid4(),
        run_id=run_id,
        interrupt_id="interrupt-1",
        approval_type="campaign_launch_approval_required",
        payload={"product_sku": "NOVA-AUDIO-001"},
        status=ApprovalRequestStatus.PENDING,
        reviewer=None,
        comment=None,
        decided_at=None,
        created_at=now,
        updated_at=now,
    )

    assert run.product_id == product_id
    assert approval.status is ApprovalRequestStatus.PENDING
