from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from commercepilot.db.session import get_db
from commercepilot.main import app
from commercepilot.models.enums import PriceChangeType
from commercepilot.models.market import (
    MarketCompetitorView,
    MarketOverview,
    MarketSnapshotResult,
)
from commercepilot.services.market_api import MarketSnapshotConflictError


def override_db() -> MagicMock:
    return MagicMock()


client = TestClient(app)
app.dependency_overrides[get_db] = override_db


def make_market_view() -> MarketCompetitorView:
    return MarketCompetitorView(
        competitor_product_id=uuid4(),
        competitor_sku="AP-CM2",
        competitor_name="AudioPeak",
        competitor_product_name="ComfortMax 2",
        current_snapshot_id=uuid4(),
        previous_snapshot_id=uuid4(),
        previous_price=Decimal("109.99"),
        current_price=Decimal("89.99"),
        currency="USD",
        change_type=PriceChangeType.DECREASED,
        change_amount=Decimal("-20.00"),
        change_percent=Decimal("-18.18"),
        promotion="Flash sale",
        observed_at=datetime.now(UTC),
        price_difference_from_ours=Decimal("-10.00"),
        is_cheaper_than_ours=True,
    )


@patch("commercepilot.api.market.get_market_overview")
def test_read_market_overview_returns_competitors(
    get_overview: MagicMock,
) -> None:
    view = make_market_view()
    get_overview.return_value = MarketOverview(
        product_id=uuid4(),
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        our_price=Decimal("99.99"),
        currency="USD",
        competitors=[view],
    )

    response = client.get("/api/products/nova-audio-001/market")

    assert response.status_code == 200
    assert response.json()["competitors"][0]["competitor_sku"] == "AP-CM2"
    get_overview.assert_called_once()
    assert get_overview.call_args.args[1] == "NOVA-AUDIO-001"


@patch("commercepilot.api.market.create_market_snapshot")
def test_create_market_snapshot_returns_detected_change(
    create_snapshot: MagicMock,
) -> None:
    view = make_market_view()
    create_snapshot.return_value = MarketSnapshotResult(
        **view.model_dump(),
        product_sku="NOVA-AUDIO-001",
    )

    response = client.post(
        "/api/products/NOVA-AUDIO-001/market/snapshots",
        json={
            "competitor_sku": "AP-CM2",
            "price": "89.99",
            "promotion": "Flash sale",
            "observed_at": datetime.now(UTC).isoformat(),
        },
    )

    assert response.status_code == 201
    assert response.json()["change_type"] == "decreased"
    assert response.json()["is_cheaper_than_ours"] is True


@patch("commercepilot.api.market.create_market_snapshot")
def test_create_market_snapshot_returns_conflict_for_old_timestamp(
    create_snapshot: MagicMock,
) -> None:
    create_snapshot.side_effect = MarketSnapshotConflictError(
        "observed_at must be later than the latest competitor snapshot"
    )

    response = client.post(
        "/api/products/NOVA-AUDIO-001/market/snapshots",
        json={
            "competitor_sku": "AP-CM2",
            "price": "89.99",
            "observed_at": datetime.now(UTC).isoformat(),
        },
    )

    assert response.status_code == 409
