from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.campaign import CampaignAsset, CampaignDraft
from commercepilot.models.enums import CampaignChannel


def make_campaign() -> CampaignDraft:
    product_id = uuid4()
    review_id = uuid4()
    return CampaignDraft(
        product_sku="NOVA-AUDIO-001",
        name="Commute Without Distractions",
        objective="Increase qualified product-page visits from commuters.",
        target_audience=("Daily commuters seeking focused wireless listening."),
        core_message=(
            "Balanced audio, active noise cancellation, and long battery life "
            "support focused listening throughout the day."
        ),
        assets=[
            CampaignAsset(
                channel=CampaignChannel.EMAIL,
                headline="Make every commute sound better",
                body=(
                    "Discover balanced wireless audio, active noise "
                    "cancellation, and battery life built for daily travel."
                ),
                call_to_action="Explore NovaSound Pro",
                evidence_ids=[product_id, review_id],
            ),
            CampaignAsset(
                channel=CampaignChannel.SOCIAL,
                headline="Focus on the journey",
                body=(
                    "Bring balanced sound and active noise cancellation to "
                    "your everyday commute."
                ),
                call_to_action="Learn more",
                evidence_ids=[product_id],
            ),
            CampaignAsset(
                channel=CampaignChannel.PAID_SEARCH,
                headline="Wireless audio for focused commutes",
                body=(
                    "Explore balanced sound, active noise cancellation, and "
                    "battery life designed for daily listening."
                ),
                call_to_action="Shop NovaSound Pro",
                evidence_ids=[product_id],
            ),
        ],
        duration_days=14,
        success_metrics=["Click-through rate", "Product-page conversion rate"],
        supporting_evidence_ids=[product_id, review_id],
        confidence=0.88,
    )


def test_campaign_draft_accepts_typed_assets_and_evidence() -> None:
    campaign = make_campaign()

    assert campaign.assets[0].channel is CampaignChannel.EMAIL
    assert campaign.duration_days == 14
    assert campaign.confidence == 0.88


def test_campaign_draft_requires_unique_channels() -> None:
    payload = make_campaign().model_dump()
    payload["assets"][1]["channel"] = CampaignChannel.EMAIL

    with pytest.raises(ValidationError, match="unique channels"):
        CampaignDraft.model_validate(payload)


def test_campaign_asset_evidence_must_be_in_supporting_ids() -> None:
    payload = make_campaign().model_dump()
    payload["assets"][0]["evidence_ids"] = [uuid4()]

    with pytest.raises(ValidationError, match="supporting evidence IDs"):
        CampaignDraft.model_validate(payload)


def test_campaign_draft_rejects_unknown_fields() -> None:
    payload = make_campaign().model_dump()
    payload["unapproved_discount"] = 50

    with pytest.raises(ValidationError):
        CampaignDraft.model_validate(payload)
