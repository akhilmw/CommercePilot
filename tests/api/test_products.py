from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from commercepilot.db.session import get_db
from commercepilot.main import app
from commercepilot.models.dashboard import ProductPortfolioItem
from commercepilot.models.enums import OrchestrationRunStatus, ProductStatus
from commercepilot.models.review import ReviewIngestionResult
from commercepilot.services.product_portfolio import PortfolioProductNotFoundError


def override_db() -> MagicMock:
    return MagicMock()


client = TestClient(app)
app.dependency_overrides[get_db] = override_db


def make_run() -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        thread_id=uuid4(),
        product_id=uuid4(),
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        status=OrchestrationRunStatus.COMPLETED,
        current_stage="completed",
        force_catalog_update=False,
        force_campaign_update=False,
        result={},
        error=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


@patch("commercepilot.api.products.list_product_portfolio")
def test_read_product_portfolio_returns_dashboard_summary(
    list_portfolio: MagicMock,
) -> None:
    now = datetime.now(UTC)
    item = ProductPortfolioItem(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        price=Decimal("99.99"),
        currency="USD",
        status=ProductStatus.ACTIVE,
        catalog_version=5,
        review_count=25,
        competitor_count=3,
        pending_approval_count=0,
        latest_run=None,
        updated_at=now,
    )
    list_portfolio.return_value = [item]

    response = client.get("/api/products")

    assert response.status_code == 200
    assert response.json()[0]["sku"] == "NOVA-AUDIO-001"
    assert response.json()[0]["review_count"] == 25
    assert response.json()[0]["catalog_version"] == 5


@patch("commercepilot.api.products.list_product_runs")
def test_read_product_runs_returns_newest_history(list_runs: MagicMock) -> None:
    run = make_run()
    list_runs.return_value = [run]

    response = client.get("/api/products/nova-audio-001/runs?limit=10")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(run.id)
    assert list_runs.call_count == 1
    assert list_runs.call_args.args[1] == "NOVA-AUDIO-001"
    assert list_runs.call_args.kwargs == {"limit": 10}


@patch("commercepilot.api.products.list_product_runs")
def test_read_product_runs_returns_404_for_unknown_product(
    list_runs: MagicMock,
) -> None:
    list_runs.side_effect = PortfolioProductNotFoundError(
        "Product not found: MISSING-SKU"
    )

    response = client.get("/api/products/MISSING-SKU/runs")

    assert response.status_code == 404


def test_read_product_runs_validates_limit() -> None:
    response = client.get("/api/products/NOVA-AUDIO-001/runs?limit=0")

    assert response.status_code == 422


@patch("commercepilot.api.products.ingest_reviews")
def test_operator_can_append_simulated_review(ingest: MagicMock) -> None:
    ingest.return_value = ReviewIngestionResult(
        product_sku="NOVA-WEAR-001", received=1, created=1, skipped=0
    )
    response = client.post(
        "/api/products/nova-wear-001/reviews",
        json={"rating": 2, "body": "The watch strap irritated my wrist."},
    )
    assert response.status_code == 201
    session, sku, reviews = ingest.call_args.args
    assert sku == "NOVA-WEAR-001"
    assert len(reviews) == 1
    assert reviews[0].source == "review_simulator"
    assert reviews[0].rating == 2
    assert reviews[0].verified_purchase is False
    session.commit.assert_called_once()


def test_simulated_review_rejects_invalid_input() -> None:
    response = client.post(
        "/api/products/NOVA-WEAR-001/reviews",
        json={"rating": 2, "body": "There is a null\x00 character here."},
    )
    assert response.status_code == 422
