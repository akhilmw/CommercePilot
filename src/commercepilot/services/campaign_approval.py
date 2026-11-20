from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovedAction, CampaignDraftRecord, Product
from commercepilot.models.enums import CampaignDraftStatus
from commercepilot.models.orchestration import HumanApprovalDecision

CAMPAIGN_LAUNCH_ACTION_TYPE = "launch_campaign"


def _approved_campaign_payload(
    draft: CampaignDraftRecord,
    product: Product,
    decision: HumanApprovalDecision,
) -> dict[str, Any]:
    return {
        "draft_id": str(draft.id),
        "product_id": str(product.id),
        "product_sku": product.sku,
        "source_catalog_version": draft.source_catalog_version,
        "source_price": str(draft.source_price),
        "currency": product.currency,
        "name": draft.name,
        "objective": draft.objective,
        "target_audience": draft.target_audience,
        "core_message": draft.core_message,
        "assets": draft.assets,
        "duration_days": draft.duration_days,
        "success_metrics": draft.success_metrics,
        "supporting_evidence_ids": draft.supporting_evidence_ids,
        "confidence": str(draft.confidence),
        "approval_comment": decision.comment,
    }


def process_campaign_approval(
    session: Session,
    draft_id: UUID,
    decision: HumanApprovalDecision,
) -> ApprovedAction | None:
    draft = session.get(CampaignDraftRecord, draft_id)
    if draft is None:
        raise ValueError(f"Unknown campaign draft: {draft_id}")

    if not decision.approved:
        if draft.status is CampaignDraftStatus.REJECTED:
            return None
        if draft.status is not CampaignDraftStatus.DRAFT:
            raise ValueError(
                f"Cannot reject campaign draft with status: {draft.status}"
            )
        draft.status = CampaignDraftStatus.REJECTED
        draft.rejected_at = datetime.now(UTC)
        session.commit()
        return None

    if draft.status not in {
        CampaignDraftStatus.DRAFT,
        CampaignDraftStatus.APPROVED,
    }:
        raise ValueError(f"Cannot approve campaign draft with status: {draft.status}")

    product = session.get(Product, draft.product_id)
    if product is None:
        raise ValueError(f"Campaign draft product not found: {draft.product_id}")
    if product.catalog_version != draft.source_catalog_version:
        raise ValueError(
            "Campaign draft is stale: expected catalog version "
            f"{draft.source_catalog_version}, current version "
            f"{product.catalog_version}."
        )
    if product.price != draft.source_price:
        raise ValueError(
            "Campaign draft is stale: expected price "
            f"{draft.source_price}, current price {product.price}."
        )

    payload = _approved_campaign_payload(draft, product, decision)
    idempotency_key = f"campaign-launch:{draft.id}"
    existing = session.get(ApprovedAction, draft.id)
    if existing is not None:
        if (
            existing.action_type != CAMPAIGN_LAUNCH_ACTION_TYPE
            or existing.idempotency_key != idempotency_key
            or existing.payload != payload
        ):
            raise ValueError(
                f"Existing approved action does not match draft: {draft.id}"
            )
        return existing

    approved_at = datetime.now(UTC)
    action = ApprovedAction(
        id=draft.id,
        action_type=CAMPAIGN_LAUNCH_ACTION_TYPE,
        idempotency_key=idempotency_key,
        payload=payload,
        status="approved",
        approved_by=decision.reviewer,
        approved_at=approved_at,
    )
    draft.status = CampaignDraftStatus.APPROVED
    draft.approved_at = approved_at
    session.add(action)
    session.commit()
    return action
