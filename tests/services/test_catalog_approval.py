from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovedAction, CatalogDraftRecord, Product
from commercepilot.models.enums import CatalogDraftStatus
from commercepilot.models.orchestration import HumanApprovalDecision
from commercepilot.services.catalog_approval import process_catalog_approval


def make_product(*, catalog_version: int = 1) -> Product:
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        catalog_version=catalog_version,
    )


def make_draft(
    product: Product,
    *,
    status: CatalogDraftStatus = CatalogDraftStatus.DRAFT,
    expected_version: int = 1,
) -> CatalogDraftRecord:
    return CatalogDraftRecord(
        id=uuid4(),
        product_id=product.id,
        expected_catalog_version=expected_version,
        seo_title="NovaSound Pro Wireless ANC Headphones",
        meta_description=(
            "Wireless headphones with active noise cancellation and long "
            "battery life for focused everyday listening."
        ),
        product_description=(
            "NovaSound Pro combines balanced wireless audio with active noise "
            "cancellation for commuting and focused everyday listening."
        ),
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
        status=status,
    )


def approval_decision(*, approved: bool) -> HumanApprovalDecision:
    return HumanApprovalDecision(
        approved=approved,
        reviewer="catalog-reviewer",
        comment="Reviewed against the generated diff.",
    )


def test_approval_freezes_exact_catalog_payload() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    draft = make_draft(product)
    session.get.side_effect = [draft, product, None]

    action = process_catalog_approval(
        session,
        draft.id,
        approval_decision(approved=True),
    )

    assert isinstance(action, ApprovedAction)
    assert action.id == draft.id
    assert action.action_type == "publish_catalog_update"
    assert action.idempotency_key == f"catalog-publish:{draft.id}"
    assert action.payload["draft_id"] == str(draft.id)
    assert action.payload["expected_catalog_version"] == 1
    assert action.payload["seo_title"] == draft.seo_title
    assert action.payload["feature_bullets"] == draft.feature_bullets
    assert action.payload["approval_comment"] == (
        "Reviewed against the generated diff."
    )
    assert draft.status is CatalogDraftStatus.APPROVED
    assert draft.approved_at is not None
    session.add.assert_called_once_with(action)
    session.commit.assert_called_once()


def test_rejection_closes_draft_without_approved_action() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    draft = make_draft(product)
    session.get.return_value = draft

    action = process_catalog_approval(
        session,
        draft.id,
        approval_decision(approved=False),
    )

    assert action is None
    assert draft.status is CatalogDraftStatus.REJECTED
    assert draft.rejected_at is not None
    session.add.assert_not_called()
    session.commit.assert_called_once()


def test_approval_rejects_stale_catalog_version() -> None:
    session = MagicMock(spec=Session)
    product = make_product(catalog_version=2)
    draft = make_draft(product, expected_version=1)
    session.get.side_effect = [draft, product]

    with pytest.raises(ValueError, match="expected version 1, current version 2"):
        process_catalog_approval(
            session,
            draft.id,
            approval_decision(approved=True),
        )

    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_approval_is_idempotent_for_matching_existing_action() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    draft = make_draft(product, status=CatalogDraftStatus.APPROVED)
    decision = approval_decision(approved=True)
    existing = ApprovedAction(
        id=draft.id,
        action_type="publish_catalog_update",
        idempotency_key=f"catalog-publish:{draft.id}",
        payload={
            "draft_id": str(draft.id),
            "product_id": str(product.id),
            "product_sku": product.sku,
            "expected_catalog_version": 1,
            "seo_title": draft.seo_title,
            "meta_description": draft.meta_description,
            "product_description": draft.product_description,
            "feature_bullets": draft.feature_bullets,
            "seo_keywords": draft.seo_keywords,
            "target_audience": draft.target_audience,
            "supporting_evidence_ids": draft.supporting_evidence_ids,
            "confidence": str(draft.confidence),
            "approval_comment": decision.comment,
        },
        status="approved",
        approved_by=decision.reviewer,
    )
    session.get.side_effect = [draft, product, existing]

    action = process_catalog_approval(session, draft.id, decision)

    assert action is existing
    session.add.assert_not_called()
    session.commit.assert_not_called()
