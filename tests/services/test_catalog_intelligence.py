from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from commercepilot.db.models import Product
from commercepilot.models.competitor import CompetitorFinding, CompetitorInsight
from commercepilot.models.enums import (
    CompetitiveThreatLevel,
    ProductStatus,
    ReviewSentiment,
)
from commercepilot.models.review import ReviewInsight, ReviewTheme
from commercepilot.services.catalog_intelligence import load_catalog_evidence


def make_product() -> Product:
    timestamp = datetime(2026, 11, 19, tzinfo=UTC)
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless headphones for focused everyday listening.",
        specifications={"battery_life_hours": 40},
        price=Decimal("109.99"),
        currency="USD",
        status=ProductStatus.ACTIVE,
        catalog_version=1,
        feature_bullets=[],
        seo_keywords=[],
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_review_insight(product_sku: str = "NOVA-AUDIO-001") -> ReviewInsight:
    return ReviewInsight(
        product_sku=product_sku,
        overall_sentiment=ReviewSentiment.POSITIVE,
        executive_summary=(
            "Customers value the product's battery life and audio quality."
        ),
        strengths=[
            ReviewTheme(
                theme="Battery life",
                summary="Customers report strong battery performance.",
                evidence_review_ids=[uuid4()],
            )
        ],
        complaints=[],
        requested_improvements=[],
        confidence=0.9,
    )


def make_competitor_insight(
    *,
    product_sku: str = "NOVA-AUDIO-001",
    our_price: Decimal = Decimal("109.99"),
) -> CompetitorInsight:
    return CompetitorInsight(
        product_sku=product_sku,
        our_price=our_price,
        currency="USD",
        overall_threat_level=CompetitiveThreatLevel.HIGH,
        market_summary=(
            "Competitors are applying price pressure in wireless headphones."
        ),
        findings=[
            CompetitorFinding(
                competitor_product_id=uuid4(),
                competitor_name="AudioPeak",
                threat_level=CompetitiveThreatLevel.HIGH,
                summary="AudioPeak is running a temporary price promotion.",
                evidence_snapshot_ids=[uuid4()],
            )
        ],
        recommended_actions=[],
        confidence=0.88,
    )


def test_load_catalog_evidence_combines_authoritative_product_and_insights(
) -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.return_value = product

    evidence = load_catalog_evidence(
        session,
        product.sku,
        make_review_insight(),
        make_competitor_insight(),
    )

    assert evidence.product.id == product.id
    assert evidence.product.price == Decimal("109.99")
    assert evidence.review_insight.product_sku == product.sku
    assert evidence.competitor_insight.product_sku == product.sku


def test_load_catalog_evidence_rejects_unknown_product() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError, match="Unknown product SKU"):
        load_catalog_evidence(
            session,
            "UNKNOWN-SKU",
            make_review_insight(),
            make_competitor_insight(),
        )


def test_catalog_evidence_rejects_mismatched_agent_sku() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = make_product()

    with pytest.raises(ValidationError, match="Review insight SKU"):
        load_catalog_evidence(
            session,
            "NOVA-AUDIO-001",
            make_review_insight("OTHER-AUDIO-001"),
            make_competitor_insight(),
        )


def test_catalog_evidence_rejects_stale_competitor_price() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = make_product()

    with pytest.raises(ValidationError, match="current product price"):
        load_catalog_evidence(
            session,
            "NOVA-AUDIO-001",
            make_review_insight(),
            make_competitor_insight(our_price=Decimal("129.99")),
        )
