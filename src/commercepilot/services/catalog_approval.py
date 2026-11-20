from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovedAction, CatalogDraftRecord, Product
from commercepilot.models.enums import CatalogDraftStatus
from commercepilot.models.orchestration import HumanApprovalDecision

CATALOG_PUBLISH_ACTION_TYPE = "publish_catalog_update"


def _approved_catalog_payload(
    draft: CatalogDraftRecord,
    product: Product,
    decision: HumanApprovalDecision,
) -> dict[str, Any]:
    return {
        "draft_id": str(draft.id),
        "product_id": str(product.id),
        "product_sku": product.sku,
        "expected_catalog_version": draft.expected_catalog_version,
        "seo_title": draft.seo_title,
        "meta_description": draft.meta_description,
        "product_description": draft.product_description,
        "feature_bullets": draft.feature_bullets,
        "seo_keywords": draft.seo_keywords,
        "target_audience": draft.target_audience,
        "supporting_evidence_ids": draft.supporting_evidence_ids,
        "confidence": str(draft.confidence),
        "approval_comment": decision.comment,
    }


def process_catalog_approval(
    session: Session,
    draft_id: UUID,
    decision: HumanApprovalDecision,
) -> ApprovedAction | None:
    draft = session.get(CatalogDraftRecord, draft_id)
    if draft is None:
        raise ValueError(f"Unknown catalog draft: {draft_id}")

    if not decision.approved:
        if draft.status is CatalogDraftStatus.REJECTED:
            return None
        if draft.status is not CatalogDraftStatus.DRAFT:
            raise ValueError(
                f"Cannot reject catalog draft with status: {draft.status}"
            )
        draft.status = CatalogDraftStatus.REJECTED
        draft.rejected_at = datetime.now(UTC)
        session.commit()
        return None

    if draft.status not in {
        CatalogDraftStatus.DRAFT,
        CatalogDraftStatus.APPROVED,
    }:
        raise ValueError(
            f"Cannot approve catalog draft with status: {draft.status}"
        )

    product = session.get(Product, draft.product_id)
    if product is None:
        raise ValueError(f"Catalog draft product not found: {draft.product_id}")
    if product.catalog_version != draft.expected_catalog_version:
        raise ValueError(
            "Catalog draft is stale: expected version "
            f"{draft.expected_catalog_version}, current version "
            f"{product.catalog_version}."
        )

    payload = _approved_catalog_payload(draft, product, decision)
    idempotency_key = f"catalog-publish:{draft.id}"
    existing = session.get(ApprovedAction, draft.id)
    if existing is not None:
        if (
            existing.action_type != CATALOG_PUBLISH_ACTION_TYPE
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
        action_type=CATALOG_PUBLISH_ACTION_TYPE,
        idempotency_key=idempotency_key,
        payload=payload,
        status="approved",
        approved_by=decision.reviewer,
        approved_at=approved_at,
    )
    draft.status = CatalogDraftStatus.APPROVED
    draft.approved_at = approved_at
    session.add(action)
    session.commit()
    return action
