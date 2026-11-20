from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import CampaignDraftRecord, Product
from commercepilot.models.campaign import CampaignDraft, CampaignEvidenceSet
from commercepilot.models.enums import CampaignDraftStatus


def save_campaign_draft(
    session: Session,
    draft: CampaignDraft,
    evidence: CampaignEvidenceSet,
) -> CampaignDraftRecord:
    product = session.scalar(select(Product).where(Product.sku == draft.product_sku))
    if product is None:
        raise ValueError(f"Unknown product SKU: {draft.product_sku}")
    if product.id != evidence.product.id:
        raise ValueError("Campaign evidence product does not match the database.")
    if product.catalog_version != evidence.product.catalog_version:
        raise ValueError(
            "Campaign evidence is stale: catalog version changed from "
            f"{evidence.product.catalog_version} to {product.catalog_version}."
        )
    if product.price != evidence.product.price:
        raise ValueError(
            "Campaign evidence is stale: product price changed from "
            f"{evidence.product.price} to {product.price}."
        )

    record = CampaignDraftRecord(
        product_id=product.id,
        source_catalog_version=product.catalog_version,
        source_price=product.price,
        name=draft.name,
        objective=draft.objective,
        target_audience=draft.target_audience,
        core_message=draft.core_message,
        assets=[asset.model_dump(mode="json") for asset in draft.assets],
        duration_days=draft.duration_days,
        success_metrics=draft.success_metrics,
        supporting_evidence_ids=[
            str(evidence_id) for evidence_id in draft.supporting_evidence_ids
        ],
        confidence=Decimal(str(draft.confidence)),
        status=CampaignDraftStatus.DRAFT,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
