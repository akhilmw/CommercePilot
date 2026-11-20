from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import CatalogDraftRecord, Product
from commercepilot.models.enums import CatalogDraftStatus
from commercepilot.services.catalog_comparison import build_catalog_comparison


def make_product(*, catalog_version: int = 1) -> Product:
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        description="Current wireless headphone description.",
        price=Decimal("109.99"),
        catalog_version=catalog_version,
        seo_title=None,
        meta_description=None,
        feature_bullets=[],
        seo_keywords=[],
        target_audience=None,
    )


def make_draft(product: Product, *, expected_version: int = 1) -> CatalogDraftRecord:
    return CatalogDraftRecord(
        id=uuid4(),
        product_id=product.id,
        expected_catalog_version=expected_version,
        seo_title="NovaSound Pro Wireless ANC Headphones",
        meta_description=(
            "Wireless headphones with active noise cancellation and long "
            "battery life for focused everyday listening."
        ),
        product_description="Current wireless headphone description.",
        feature_bullets=[
            {
                "text": "Up to 30 hours of battery life.",
                "evidence_ids": [str(uuid4())],
            }
        ],
        seo_keywords=["wireless headphones", "ANC headphones"],
        target_audience="Commuters and focused professionals.",
        supporting_evidence_ids=[str(uuid4())],
        confidence=Decimal("0.860"),
        status=CatalogDraftStatus.DRAFT,
    )


def test_build_catalog_comparison_returns_structured_field_diffs() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    draft = make_draft(product)
    session.get.side_effect = [draft, product]

    comparison = build_catalog_comparison(session, draft.id)

    assert comparison.draft_id == draft.id
    assert comparison.product_sku == product.sku
    assert comparison.is_stale is False
    assert comparison.has_changes is True
    fields = {field.field: field for field in comparison.fields}
    assert fields["seo_title"].current_value == "NovaSound Pro"
    assert fields["seo_title"].proposed_value == draft.seo_title
    assert fields["seo_title"].changed is True
    assert fields["product_description"].changed is False
    assert fields["feature_bullets"].proposed_value == draft.feature_bullets


def test_build_catalog_comparison_flags_stale_draft() -> None:
    session = MagicMock(spec=Session)
    product = make_product(catalog_version=2)
    draft = make_draft(product, expected_version=1)
    session.get.side_effect = [draft, product]

    comparison = build_catalog_comparison(session, draft.id)

    assert comparison.current_catalog_version == 2
    assert comparison.expected_catalog_version == 1
    assert comparison.is_stale is True


def test_build_catalog_comparison_rejects_unknown_draft() -> None:
    session = MagicMock(spec=Session)
    draft_id = uuid4()
    session.get.return_value = None

    with pytest.raises(ValueError, match="Unknown catalog draft"):
        build_catalog_comparison(session, draft_id)
