from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import CatalogDraftRecord, Product
from commercepilot.models.catalog import CatalogDraft
from commercepilot.models.enums import CatalogDraftStatus


def save_catalog_draft(
    session: Session,
    draft: CatalogDraft,
) -> CatalogDraftRecord:
    product = session.scalar(
        select(Product).where(Product.sku == draft.product_sku)
    )
    if product is None:
        raise ValueError(f"Unknown product SKU: {draft.product_sku}")

    record = CatalogDraftRecord(
        product_id=product.id,
        expected_catalog_version=product.catalog_version,
        seo_title=draft.seo_title,
        meta_description=draft.meta_description,
        product_description=draft.product_description,
        feature_bullets=[
            bullet.model_dump(mode="json")
            for bullet in draft.feature_bullets
        ],
        seo_keywords=draft.seo_keywords,
        target_audience=draft.target_audience,
        supporting_evidence_ids=[
            str(evidence_id)
            for evidence_id in draft.supporting_evidence_ids
        ],
        confidence=Decimal(str(draft.confidence)),
        status=CatalogDraftStatus.DRAFT,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
