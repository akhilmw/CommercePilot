from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from commercepilot.db.session import get_db
from commercepilot.main import app
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.models.orchestration_api import ApprovalInboxItem


def override_db() -> MagicMock:
    return MagicMock()


client = TestClient(app)
app.dependency_overrides[get_db] = override_db


@patch("commercepilot.api.approvals.list_approval_inbox")
def test_read_approval_inbox_returns_product_context(
    list_inbox: MagicMock,
) -> None:
    now = datetime.now(UTC)
    item = ApprovalInboxItem(
        id=uuid4(),
        run_id=uuid4(),
        interrupt_id="interrupt-1",
        approval_type="campaign_launch_approval_required",
        payload={},
        status=ApprovalRequestStatus.PENDING,
        reviewer=None,
        comment=None,
        decided_at=None,
        created_at=now,
        updated_at=now,
        product_id=uuid4(),
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        run_status=OrchestrationRunStatus.AWAITING_APPROVAL,
        run_current_stage="campaign_launch_approval_required",
    )
    list_inbox.return_value = [item]

    response = client.get("/api/approvals")

    assert response.status_code == 200
    assert response.json()[0]["product_sku"] == "NOVA-AUDIO-001"
    assert response.json()[0]["approval_type"] == (
        "campaign_launch_approval_required"
    )


@patch("commercepilot.api.approvals.list_approval_inbox")
def test_read_approval_inbox_accepts_status_filter(list_inbox: MagicMock) -> None:
    list_inbox.return_value = []

    response = client.get("/api/approvals?status=approved&limit=10")

    assert response.status_code == 200
    assert list_inbox.call_args.kwargs == {
        "approval_status": ApprovalRequestStatus.APPROVED,
        "limit": 10,
    }
