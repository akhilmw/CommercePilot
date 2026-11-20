from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import CatalogDraftRecord, Product
from commercepilot.models.catalog import CatalogBullet, CatalogDraft
from commercepilot.models.enums import CatalogDraftStatus
from commercepilot.services.catalog_persistence import save_catalog_draft


def make_draft() -> CatalogDraft:
    product_evidence_id = uuid4()
    review_evidence_id = uuid4()
    return CatalogDraft(
        product_sku="NOVA-AUDIO-001",
        seo_title="NovaSound Pro Wireless ANC Headphones — 30H Battery",
        meta_description=(
            "Wireless over-ear headphones with active noise cancellation, "
            "Bluetooth 5.3 connectivity, and up to 30 hours of battery life."
        ),
        product_description=(
            "NovaSound Pro combines detailed wireless audio, active noise "
            "cancellation, Bluetooth 5.3 connectivity, and up to 30 hours of "
            "battery life for commuting, travel, and focused everyday listening."
        ),
        feature_bullets=[
            CatalogBullet(
                text="Up to 30 hours of battery life for extended listening.",
                evidence_ids=[product_evidence_id],
            ),
            CatalogBullet(
                text="Active noise cancellation helps reduce distractions.",
                evidence_ids=[product_evidence_id, review_evidence_id],
            ),
            CatalogBullet(
                text="Balanced wireless audio supports everyday listening.",
                evidence_ids=[review_evidence_id],
            ),
        ],
        seo_keywords=[
            "wireless headphones",
            "ANC headphones",
            "30 hour battery headphones",
        ],
        target_audience=(
            "Commuters and professionals seeking focused wireless listening."
        ),
        supporting_evidence_ids=[
            product_evidence_id,
            review_evidence_id,
        ],
        confidence=0.86,
    )


def test_save_catalog_draft_snapshots_current_catalog_version() -> None:
    session = MagicMock(spec=Session)
    product = Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        catalog_version=3,
    )
    session.scalar.return_value = product
    draft = make_draft()

    record = save_catalog_draft(session, draft)

    assert isinstance(record, CatalogDraftRecord)
    assert record.product_id == product.id
    assert record.expected_catalog_version == 3
    assert record.seo_title == draft.seo_title
    assert record.feature_bullets == [
        bullet.model_dump(mode="json")
        for bullet in draft.feature_bullets
    ]
    assert record.supporting_evidence_ids == [
        str(evidence_id) for evidence_id in draft.supporting_evidence_ids
    ]
    assert record.confidence == Decimal("0.86")
    assert record.status is CatalogDraftStatus.DRAFT
    session.add.assert_called_once_with(record)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(record)


def test_save_catalog_draft_rejects_unknown_product() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError, match="Unknown product SKU"):
        save_catalog_draft(session, make_draft())

    session.add.assert_not_called()
    session.commit.assert_not_called()
