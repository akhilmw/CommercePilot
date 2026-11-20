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
    ActionType,
    CompetitiveThreatLevel,
    ImprovementPriority,
    ProductStatus,
    ReviewSentiment,
    SourceAgent,
)
from commercepilot.models.orchestration import (
    ActionProposal,
    CommerceStrategy,
)
from commercepilot.models.review import ReviewInsight, ReviewTheme
from commercepilot.services.campaign_intelligence import load_campaign_evidence


def make_product() -> Product:
    timestamp = datetime(2026, 11, 20, tzinfo=UTC)
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description=(
            "Wireless over-ear headphones with active noise cancellation and "
            "up to 30 hours of battery life."
        ),
        specifications={"battery_life_hours": 30, "anc": True},
        price=Decimal("99.99"),
        currency="USD",
        status=ProductStatus.ACTIVE,
        catalog_version=3,
        seo_title="NovaSound Pro Wireless ANC Headphones",
        meta_description=(
            "Wireless headphones with active noise cancellation and long "
            "battery life for commutes and focused everyday listening."
        ),
        feature_bullets=[
            {
                "text": "Up to 30 hours of battery life.",
                "evidence_ids": [str(uuid4())],
            }
        ],
        seo_keywords=["wireless headphones", "ANC headphones"],
        target_audience="Commuters and frequent travelers.",
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_review_insight(
    product_sku: str = "NOVA-AUDIO-001",
) -> ReviewInsight:
    return ReviewInsight(
        product_sku=product_sku,
        overall_sentiment=ReviewSentiment.POSITIVE,
        executive_summary=(
            "Customers value the balanced sound and dependable battery life."
        ),
        strengths=[
            ReviewTheme(
                theme="Balanced sound",
                summary="Customers praise clear vocals and controlled bass.",
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
    our_price: Decimal = Decimal("99.99"),
) -> CompetitorInsight:
    return CompetitorInsight(
        product_sku=product_sku,
        our_price=our_price,
        currency="USD",
        overall_threat_level=CompetitiveThreatLevel.MEDIUM,
        market_summary=(
            "Competitor pricing remains active but does not require an "
            "immediate product mutation."
        ),
        findings=[
            CompetitorFinding(
                competitor_product_id=uuid4(),
                competitor_name="AudioPeak",
                threat_level=CompetitiveThreatLevel.MEDIUM,
                summary="AudioPeak continues a temporary promotion.",
                evidence_snapshot_ids=[uuid4()],
            )
        ],
        recommended_actions=[],
        confidence=0.84,
    )


def make_strategy(product_sku: str = "NOVA-AUDIO-001") -> CommerceStrategy:
    return CommerceStrategy(
        product_sku=product_sku,
        situation_summary=(
            "Customer strengths support a focused campaign while competitor "
            "pricing remains under observation."
        ),
        strategic_objectives=[
            "Increase qualified traffic using evidence-backed messaging."
        ],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.DRAFT_CAMPAIGN,
                title="Draft a commuter-focused campaign",
                description=("Create channel-specific copy based on approved claims."),
                rationale=("Review evidence supports balanced audio positioning."),
                priority=ImprovementPriority.MEDIUM,
                source_agents=[SourceAgent.REVIEW],
                evidence_ids=[uuid4()],
            )
        ],
        confidence=0.86,
    )


def test_load_campaign_evidence_combines_current_published_state() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.return_value = product

    evidence = load_campaign_evidence(
        session,
        product.sku,
        make_review_insight(),
        make_competitor_insight(),
        make_strategy(),
    )

    assert evidence.product.catalog_version == 3
    assert evidence.product.price == Decimal("99.99")
    assert evidence.product.seo_title is not None
    assert evidence.strategy.product_sku == product.sku


def test_load_campaign_evidence_rejects_unknown_product() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError, match="Unknown product SKU"):
        load_campaign_evidence(
            session,
            "UNKNOWN-SKU",
            make_review_insight(),
            make_competitor_insight(),
            make_strategy(),
        )


def test_campaign_evidence_requires_published_catalog() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    product.seo_title = None
    session.scalar.return_value = product

    with pytest.raises(ValidationError, match="published product catalog"):
        load_campaign_evidence(
            session,
            product.sku,
            make_review_insight(),
            make_competitor_insight(),
            make_strategy(),
        )


def test_campaign_evidence_rejects_stale_competitor_price() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.return_value = product

    with pytest.raises(ValidationError, match="current product price"):
        load_campaign_evidence(
            session,
            product.sku,
            make_review_insight(),
            make_competitor_insight(our_price=Decimal("109.99")),
            make_strategy(),
        )


def test_campaign_evidence_rejects_mismatched_strategy() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.return_value = product

    with pytest.raises(ValidationError, match="Strategy SKU"):
        load_campaign_evidence(
            session,
            product.sku,
            make_review_insight(),
            make_competitor_insight(),
            make_strategy("OTHER-AUDIO-001"),
        )
