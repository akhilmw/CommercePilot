from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovedAction, CampaignDraftRecord, Product
from commercepilot.models.campaign import (
    CampaignAsset,
    CampaignDraft,
    CampaignEvidenceSet,
)
from commercepilot.models.enums import (
    CampaignChannel,
    CampaignDraftStatus,
)
from commercepilot.models.orchestration import HumanApprovalDecision
from commercepilot.services.campaign_approval import process_campaign_approval
from commercepilot.services.campaign_persistence import save_campaign_draft
from commercepilot.services.campaign_preview import build_campaign_launch_preview


def make_campaign_draft() -> CampaignDraft:
    product_id = uuid4()
    review_id = uuid4()
    return CampaignDraft(
        product_sku="NOVA-AUDIO-001",
        name="Commute With Focus",
        objective="Increase qualified visits from daily commuters.",
        target_audience="Daily commuters seeking focused wireless listening.",
        core_message=(
            "Balanced audio, active noise cancellation, and long battery life "
            "support focused everyday listening."
        ),
        assets=[
            CampaignAsset(
                channel=CampaignChannel.EMAIL,
                headline="Bring focus to every commute",
                body=(
                    "Explore balanced audio, active noise cancellation, and "
                    "long battery life for daily travel."
                ),
                call_to_action="Explore NovaSound Pro",
                evidence_ids=[product_id, review_id],
            ),
            CampaignAsset(
                channel=CampaignChannel.SOCIAL,
                headline="Sound made for the daily journey",
                body=(
                    "Enjoy balanced wireless sound and active noise "
                    "cancellation throughout your commute."
                ),
                call_to_action="Learn more",
                evidence_ids=[product_id, review_id],
            ),
            CampaignAsset(
                channel=CampaignChannel.PAID_SEARCH,
                headline="Wireless ANC for commuters",
                body=(
                    "Balanced sound, ANC, and long battery life for focused "
                    "everyday listening."
                ),
                call_to_action="Shop NovaSound Pro",
                evidence_ids=[product_id],
            ),
        ],
        duration_days=21,
        success_metrics=["Click-through rate", "Conversion rate"],
        supporting_evidence_ids=[product_id, review_id],
        confidence=0.88,
    )


def make_product(
    *,
    catalog_version: int = 3,
    price: Decimal = Decimal("99.99"),
) -> Product:
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        catalog_version=catalog_version,
        price=price,
        currency="USD",
    )


def make_record(
    product: Product,
    *,
    status: CampaignDraftStatus = CampaignDraftStatus.DRAFT,
    source_catalog_version: int = 3,
    source_price: Decimal = Decimal("99.99"),
) -> CampaignDraftRecord:
    draft = make_campaign_draft()
    return CampaignDraftRecord(
        id=uuid4(),
        product_id=product.id,
        source_catalog_version=source_catalog_version,
        source_price=source_price,
        name=draft.name,
        objective=draft.objective,
        target_audience=draft.target_audience,
        core_message=draft.core_message,
        assets=[asset.model_dump(mode="json") for asset in draft.assets],
        duration_days=draft.duration_days,
        success_metrics=draft.success_metrics,
        supporting_evidence_ids=[str(value) for value in draft.supporting_evidence_ids],
        confidence=Decimal("0.880"),
        status=status,
    )


def make_evidence(product: Product) -> CampaignEvidenceSet:
    evidence = MagicMock()
    evidence.product.id = product.id
    evidence.product.catalog_version = product.catalog_version
    evidence.product.price = product.price
    return evidence


def decision(*, approved: bool) -> HumanApprovalDecision:
    return HumanApprovalDecision(
        approved=approved,
        reviewer="campaign-reviewer",
        comment="Reviewed campaign copy and evidence.",
    )


def test_save_campaign_draft_snapshots_catalog_and_price() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.return_value = product
    draft = make_campaign_draft()

    record = save_campaign_draft(session, draft, make_evidence(product))

    assert record.product_id == product.id
    assert record.source_catalog_version == 3
    assert record.source_price == Decimal("99.99")
    assert record.assets == [asset.model_dump(mode="json") for asset in draft.assets]
    assert record.status is CampaignDraftStatus.DRAFT
    session.add.assert_called_once_with(record)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(record)


def test_save_campaign_draft_rejects_stale_evidence() -> None:
    session = MagicMock(spec=Session)
    current_product = make_product(catalog_version=4)
    evidence_product = make_product(catalog_version=3)
    evidence_product.id = current_product.id
    session.scalar.return_value = current_product

    with pytest.raises(ValueError, match="catalog version changed"):
        save_campaign_draft(
            session,
            make_campaign_draft(),
            make_evidence(evidence_product),
        )

    session.add.assert_not_called()


def test_campaign_preview_marks_changed_price_as_stale() -> None:
    session = MagicMock(spec=Session)
    product = make_product(price=Decimal("89.99"))
    draft = make_record(product, source_price=Decimal("99.99"))
    session.get.side_effect = [draft, product]

    preview = build_campaign_launch_preview(session, draft.id)

    assert preview.source_price == Decimal("99.99")
    assert preview.current_price == Decimal("89.99")
    assert preview.is_stale is True
    assert len(preview.assets) == 3


def test_campaign_approval_freezes_exact_launch_payload() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    draft = make_record(product)
    session.get.side_effect = [draft, product, None]

    action = process_campaign_approval(
        session,
        draft.id,
        decision(approved=True),
    )

    assert isinstance(action, ApprovedAction)
    assert action.id == draft.id
    assert action.action_type == "launch_campaign"
    assert action.idempotency_key == f"campaign-launch:{draft.id}"
    assert action.payload["source_catalog_version"] == 3
    assert action.payload["source_price"] == "99.99"
    assert action.payload["assets"] == draft.assets
    assert draft.status is CampaignDraftStatus.APPROVED
    assert draft.approved_at is not None
    session.add.assert_called_once_with(action)
    session.commit.assert_called_once()


def test_campaign_rejection_closes_draft_without_action() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    draft = make_record(product)
    session.get.return_value = draft

    action = process_campaign_approval(
        session,
        draft.id,
        decision(approved=False),
    )

    assert action is None
    assert draft.status is CampaignDraftStatus.REJECTED
    assert draft.rejected_at is not None
    session.add.assert_not_called()
    session.commit.assert_called_once()


def test_campaign_approval_rejects_stale_price() -> None:
    session = MagicMock(spec=Session)
    product = make_product(price=Decimal("89.99"))
    draft = make_record(product, source_price=Decimal("99.99"))
    session.get.side_effect = [draft, product]

    with pytest.raises(ValueError, match="expected price 99.99"):
        process_campaign_approval(
            session,
            draft.id,
            decision(approved=True),
        )

    session.add.assert_not_called()
    session.commit.assert_not_called()
