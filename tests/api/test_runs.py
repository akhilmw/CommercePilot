from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from commercepilot.db.session import get_db
from commercepilot.main import app
from commercepilot.models.enums import ApprovalRequestStatus, OrchestrationRunStatus
from commercepilot.models.orchestration_api import RunTimelineEvent, RunTimelineRead
from commercepilot.services.orchestration_approvals import (
    ApprovalRequestAlreadyDecidedError,
)
from commercepilot.services.orchestration_runs import (
    ActiveOrchestrationRunError,
    OrchestrationRunNotFoundError,
    ProductNotFoundError,
)


def make_run() -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        thread_id=uuid4(),
        product_id=uuid4(),
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        status=OrchestrationRunStatus.PENDING,
        current_stage=None,
        force_catalog_update=False,
        force_campaign_update=False,
        result=None,
        error=None,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def make_approval(run_id: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        run_id=run_id,
        interrupt_id="interrupt-1",
        approval_type="catalog_publish_approval_required",
        payload={"type": "catalog_publish_approval_required"},
        status=ApprovalRequestStatus.PENDING,
        reviewer=None,
        comment=None,
        decided_at=None,
        created_at=now,
        updated_at=now,
    )


def override_db() -> MagicMock:
    return MagicMock()


client = TestClient(app)
app.dependency_overrides[get_db] = override_db


@patch("commercepilot.api.runs.create_orchestration_run")
def test_create_run_returns_persistent_run(create_run: MagicMock) -> None:
    run = make_run()
    create_run.return_value = run

    response = client.post(
        "/api/runs",
        json={"product_sku": "NOVA-AUDIO-001"},
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(run.id)
    assert response.json()["product_sku"] == "NOVA-AUDIO-001"
    assert response.json()["status"] == "pending"


@patch("commercepilot.api.runs.create_orchestration_run")
def test_create_run_returns_404_for_unknown_product(create_run: MagicMock) -> None:
    create_run.side_effect = ProductNotFoundError(
        "Active product not found: NOVA-MISSING-001"
    )

    response = client.post(
        "/api/runs",
        json={"product_sku": "NOVA-MISSING-001"},
    )

    assert response.status_code == 404
    assert "NOVA-MISSING-001" in response.json()["detail"]


@patch("commercepilot.api.runs.create_orchestration_run")
def test_create_run_returns_409_for_active_product_run(
    create_run: MagicMock,
) -> None:
    active_run_id = uuid4()
    create_run.side_effect = ActiveOrchestrationRunError(active_run_id)

    response = client.post(
        "/api/runs",
        json={"product_sku": "NOVA-AUDIO-001"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["active_run_id"] == str(active_run_id)


@patch("commercepilot.api.runs.get_orchestration_run")
def test_read_run_returns_current_state(get_run: MagicMock) -> None:
    run = make_run()
    run.status = OrchestrationRunStatus.AWAITING_APPROVAL
    run.current_stage = "catalog_publish_approval_required"
    get_run.return_value = run

    response = client.get(f"/api/runs/{run.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"
    assert response.json()["current_stage"] == "catalog_publish_approval_required"


@patch("commercepilot.api.runs.get_orchestration_run")
def test_read_run_returns_404_for_unknown_id(get_run: MagicMock) -> None:
    run_id = uuid4()
    get_run.side_effect = OrchestrationRunNotFoundError(
        f"Orchestration run not found: {run_id}"
    )

    response = client.get(f"/api/runs/{run_id}")

    assert response.status_code == 404


@patch("commercepilot.api.runs.get_run_timeline")
def test_read_run_timeline_returns_lifecycle_events(
    get_timeline: MagicMock,
) -> None:
    run = make_run()
    now = datetime.now(UTC)
    get_timeline.return_value = RunTimelineRead(
        run_id=run.id,
        product_sku=run.product_sku,
        product_name=run.product_name,
        status=OrchestrationRunStatus.COMPLETED,
        current_stage="completed",
        events=[
            RunTimelineEvent(
                id=f"run:{run.id}:completed",
                event_type="run_completed",
                title="Intelligence cycle completed",
                status="completed",
                occurred_at=now,
            )
        ],
    )

    response = client.get(f"/api/runs/{run.id}/timeline")

    assert response.status_code == 200
    assert response.json()["events"][0]["event_type"] == "run_completed"


@patch("commercepilot.api.runs.list_approval_requests")
def test_read_approvals_returns_pending_payload(list_approvals: MagicMock) -> None:
    run_id = uuid4()
    approval = make_approval(run_id)
    list_approvals.return_value = [approval]

    response = client.get(f"/api/runs/{run_id}/approvals")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(approval.id)
    assert response.json()[0]["status"] == "pending"
    assert response.json()[0]["payload"]["type"] == (
        "catalog_publish_approval_required"
    )


@patch("commercepilot.api.runs.submit_approval_decision")
def test_decide_approval_queues_resume(submit_decision: MagicMock) -> None:
    run_id = uuid4()
    approval = make_approval(run_id)
    approval.status = ApprovalRequestStatus.APPROVED
    approval.reviewer = "local-user"
    approval.decided_at = datetime.now(UTC)
    submit_decision.return_value = approval

    response = client.post(
        f"/api/runs/{run_id}/approvals/{approval.id}",
        json={
            "approved": True,
            "reviewer": "local-user",
            "comment": "Claims verified.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["reviewer"] == "local-user"


@patch("commercepilot.api.runs.submit_approval_decision")
def test_decide_approval_returns_conflict_when_already_decided(
    submit_decision: MagicMock,
) -> None:
    run_id = uuid4()
    approval_id = uuid4()
    submit_decision.side_effect = ApprovalRequestAlreadyDecidedError(
        f"Approval request already decided: {approval_id}"
    )

    response = client.post(
        f"/api/runs/{run_id}/approvals/{approval_id}",
        json={"approved": True, "reviewer": "local-user"},
    )

    assert response.status_code == 409
