from uuid import UUID

from sqlalchemy.orm import Session

from commercepilot.db.models import CampaignDraftRecord, Product
from commercepilot.models.campaign import CampaignAsset, CampaignLaunchPreview


def build_campaign_launch_preview(
    session: Session,
    draft_id: UUID,
) -> CampaignLaunchPreview:
    draft = session.get(CampaignDraftRecord, draft_id)
    if draft is None:
        raise ValueError(f"Unknown campaign draft: {draft_id}")

    product = session.get(Product, draft.product_id)
    if product is None:
        raise ValueError(f"Campaign draft product not found: {draft.product_id}")

    return CampaignLaunchPreview(
        draft_id=draft.id,
        product_id=product.id,
        product_sku=product.sku,
        status=draft.status,
        source_catalog_version=draft.source_catalog_version,
        current_catalog_version=product.catalog_version,
        source_price=draft.source_price,
        current_price=product.price,
        is_stale=(
            draft.source_catalog_version != product.catalog_version
            or draft.source_price != product.price
        ),
        name=draft.name,
        objective=draft.objective,
        target_audience=draft.target_audience,
        core_message=draft.core_message,
        assets=[CampaignAsset.model_validate(asset) for asset in draft.assets],
        duration_days=draft.duration_days,
        success_metrics=draft.success_metrics,
        confidence=draft.confidence,
    )
