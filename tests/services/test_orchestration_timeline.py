from datetime import UTC, datetime, timedelta
from uuid import uuid4

from commercepilot.db.models import ApprovalRequest, OrchestrationRun, Product
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.services.orchestration_timeline import build_run_timeline


def test_build_completed_run_timeline_orders_approval_lifecycle() -> None:
    created_at = datetime.now(UTC) - timedelta(minutes=10)
    product = Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless over-ear headphones.",
        price=99.99,
    )
    run = OrchestrationRun(
        id=uuid4(),
        product=product,
        status=OrchestrationRunStatus.COMPLETED,
        current_stage="completed",
        created_at=created_at,
        started_at=created_at + timedelta(minutes=1),
        completed_at=created_at + timedelta(minutes=9),
    )
    approval = ApprovalRequest(
        id=uuid4(),
        run=run,
        interrupt_id="catalog-approval",
        approval_type="catalog_publish_approval_required",
        payload={},
        status=ApprovalRequestStatus.APPROVED,
        reviewer="akhil",
        comment="Verified.",
        created_at=created_at + timedelta(minutes=4),
        decided_at=created_at + timedelta(minutes=6),
    )
    run.approval_requests = [approval]

    timeline = build_run_timeline(run)

    assert [event.event_type for event in timeline.events] == [
        "run_created",
        "run_started",
        "approval_requested",
        "approval_decided",
        "run_completed",
    ]
    assert timeline.events[3].status == "approved"
    assert timeline.events[3].details["reviewer"] == "akhil"

    run.stage_events = [
        {
            "id": "stage:catalog",
            "event_type": "agent_stage",
            "title": "Catalog generation",
            "status": "completed",
            "occurred_at": (created_at + timedelta(minutes=2)).isoformat(),
            "details": {"duration_ms": 1200},
        }
    ]
    timeline = build_run_timeline(run)
    assert timeline.events[2].id == "stage:catalog"
    assert timeline.events[2].details["duration_ms"] == 1200
