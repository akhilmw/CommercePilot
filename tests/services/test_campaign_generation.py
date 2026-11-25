import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from commercepilot.models.campaign import (
    CampaignAsset,
    CampaignClaimVerification,
    CampaignDraft,
    CampaignEvidenceSet,
    CampaignSemanticVerification,
)
from commercepilot.models.competitor import CompetitorFinding, CompetitorInsight
from commercepilot.models.enums import (
    ActionType,
    CampaignChannel,
    CompetitiveThreatLevel,
    ImprovementPriority,
    ProductStatus,
    ReviewSentiment,
    SourceAgent,
)
from commercepilot.models.orchestration import ActionProposal, CommerceStrategy
from commercepilot.models.product import ProductRead
from commercepilot.models.review import ReviewInsight, ReviewTheme
from commercepilot.services.campaign_generation import (
    CampaignVerificationResponseError,
    generate_campaign_draft,
    validate_campaign_draft,
    verify_campaign_draft_semantics,
)


def make_evidence() -> CampaignEvidenceSet:
    product_id = uuid4()
    review_id = uuid4()
    snapshot_id = uuid4()
    timestamp = datetime(2026, 11, 20, tzinfo=UTC)
    review_insight = ReviewInsight(
        product_sku="NOVA-AUDIO-001",
        overall_sentiment=ReviewSentiment.POSITIVE,
        executive_summary=(
            "Customers consistently value balanced sound and battery life."
        ),
        strengths=[
            ReviewTheme(
                theme="Balanced sound",
                summary="Customers praise clear vocals and controlled bass.",
                evidence_review_ids=[review_id],
            )
        ],
        complaints=[],
        requested_improvements=[],
        confidence=0.91,
    )
    competitor_insight = CompetitorInsight(
        product_sku="NOVA-AUDIO-001",
        our_price=Decimal("99.99"),
        currency="USD",
        overall_threat_level=CompetitiveThreatLevel.MEDIUM,
        market_summary=(
            "Competitor pricing remains active and should inform positioning."
        ),
        findings=[
            CompetitorFinding(
                competitor_product_id=uuid4(),
                competitor_name="AudioPeak",
                threat_level=CompetitiveThreatLevel.MEDIUM,
                summary="AudioPeak is running a temporary promotion.",
                evidence_snapshot_ids=[snapshot_id],
            )
        ],
        recommended_actions=[],
        confidence=0.84,
    )
    strategy = CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary=(
            "Customer strengths support an evidence-backed commuter campaign."
        ),
        strategic_objectives=["Increase qualified product-page traffic."],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.DRAFT_CAMPAIGN,
                title="Draft a commuter campaign",
                description="Create evidence-backed multi-channel copy.",
                rationale="Review evidence supports balanced audio messaging.",
                priority=ImprovementPriority.MEDIUM,
                source_agents=[SourceAgent.REVIEW],
                evidence_ids=[review_id],
            )
        ],
        confidence=0.86,
    )
    return CampaignEvidenceSet(
        product=ProductRead(
            id=product_id,
            sku="NOVA-AUDIO-001",
            name="NovaSound Pro",
            category="wireless-headphones",
            description=(
                "Wireless over-ear headphones with active noise cancellation "
                "and up to 30 hours of battery life."
            ),
            specifications={"battery_life_hours": 30, "anc": True},
            price=Decimal("99.99"),
            currency="USD",
            status=ProductStatus.ACTIVE,
            catalog_version=3,
            seo_title="NovaSound Pro Wireless ANC Headphones",
            meta_description=(
                "Wireless headphones with active noise cancellation and long "
                "battery life for everyday listening."
            ),
            feature_bullets=[
                {
                    "text": "Up to 30 hours of battery life.",
                    "evidence_ids": [str(product_id)],
                }
            ],
            seo_keywords=["wireless headphones", "ANC headphones"],
            target_audience="Commuters and frequent travelers.",
            created_at=timestamp,
            updated_at=timestamp,
        ),
        review_insight=review_insight,
        competitor_insight=competitor_insight,
        strategy=strategy,
    )


def make_draft(evidence: CampaignEvidenceSet) -> CampaignDraft:
    product_id = evidence.product.id
    review_id = evidence.review_insight.strengths[0].evidence_review_ids[0]
    return CampaignDraft(
        product_sku=evidence.product.sku,
        name="Commute With Focus",
        objective="Increase qualified visits from daily commuters.",
        target_audience="Daily commuters seeking focused wireless listening.",
        core_message=(
            "NovaSound Pro combines balanced audio, active noise cancellation, "
            "and long battery life for daily listening."
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
                    "cancellation wherever your commute takes you."
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
                evidence_ids=[product_id, review_id],
            ),
        ],
        duration_days=14,
        success_metrics=["Click-through rate", "Product-page conversion rate"],
        supporting_evidence_ids=[product_id, review_id],
        confidence=0.88,
    )


def supported_verification(draft: CampaignDraft) -> CampaignSemanticVerification:
    claim_ids = [
        "target_audience",
        "core_message",
        *(f"asset_{asset.channel.value}" for asset in draft.assets),
    ]
    return CampaignSemanticVerification(
        results=[
            CampaignClaimVerification(
                claim_id=claim_id,
                supported=True,
                rationale="The cited evidence directly supports this claim.",
            )
            for claim_id in claim_ids
        ]
    )


def test_generate_campaign_draft_returns_verified_output() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=draft),
        MagicMock(output_parsed=supported_verification(draft)),
    ]

    result = generate_campaign_draft(evidence, client, "test-model")

    assert result == draft
    assert client.responses.parse.call_count == 2
    generation_request = client.responses.parse.call_args_list[0].kwargs
    assert generation_request["text_format"] is CampaignDraft
    request_payload = json.loads(generation_request["input"])
    assert "customer_claim_guardrails" in request_payload


def test_generate_campaign_extracts_complaints_as_claim_guardrails() -> None:
    evidence = make_evidence()
    review_id = evidence.review_insight.strengths[0].evidence_review_ids[0]
    evidence.review_insight.complaints = [
        ReviewTheme(
            theme="Bluetooth instability",
            summary="Customers report intermittent Bluetooth disconnections.",
            evidence_review_ids=[review_id],
        )
    ]
    draft = make_draft(evidence)
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=draft),
        MagicMock(output_parsed=supported_verification(draft)),
    ]

    generate_campaign_draft(evidence, client, "test-model")

    request = json.loads(client.responses.parse.call_args_list[0].kwargs["input"])
    guardrails = request["customer_claim_guardrails"]
    assert guardrails["documented_complaints"][0]["theme"] == (
        "Bluetooth instability"
    )
    assert "Never positively qualify" in guardrails["claim_rule"]


def test_validate_campaign_rejects_unknown_evidence() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.supporting_evidence_ids.append(uuid4())

    with pytest.raises(ValueError, match="unknown evidence IDs"):
        validate_campaign_draft(draft, evidence)


def test_validate_campaign_rejects_competitor_evidence_in_asset() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    snapshot_id = evidence.competitor_insight.findings[0].evidence_snapshot_ids[0]
    draft.supporting_evidence_ids.append(snapshot_id)
    draft.assets[0].evidence_ids.append(snapshot_id)

    with pytest.raises(ValueError, match="cannot cite competitor evidence"):
        validate_campaign_draft(draft, evidence)


def test_validate_campaign_rejects_uuid_leak_in_customer_copy() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.assets[0].body = (
        "Explore balanced wireless audio for everyday listening. Evidence: "
        f"{evidence.product.id}."
    )

    with pytest.raises(ValueError, match="leaked evidence UUIDs"):
        validate_campaign_draft(draft, evidence)


def test_validate_campaign_enforces_paid_search_limits() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    paid_search = next(
        asset for asset in draft.assets if asset.channel is CampaignChannel.PAID_SEARCH
    )
    paid_search.headline = "A paid search headline that is much too long"

    with pytest.raises(ValueError, match="paid_search headline exceeds 30"):
        validate_campaign_draft(draft, evidence)


def test_semantic_verifier_rejects_unsupported_campaign_claim() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    verification = supported_verification(draft)
    verification.results[1] = CampaignClaimVerification(
        claim_id="core_message",
        supported=False,
        rationale="The evidence does not support the claimed product feature.",
    )
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = verification

    with pytest.raises(ValueError, match="core_message.*does not support"):
        verify_campaign_draft_semantics(
            draft,
            evidence,
            client,
            "test-model",
        )


@pytest.mark.parametrize("invalid_result", ["missing", "unexpected", "duplicate"])
def test_bad_verifier_ids_retry_without_regenerating_draft(
    invalid_result: str,
) -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    expected = supported_verification(draft)
    malformed = expected.model_copy(deep=True)
    if invalid_result == "missing":
        malformed.results.pop()
    elif invalid_result == "unexpected":
        malformed.results[-1].claim_id = "asset_unknown"
    else:
        malformed.results[-1] = malformed.results[0]
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=draft),
        MagicMock(output_parsed=malformed),
        MagicMock(output_parsed=expected),
    ]

    assert generate_campaign_draft(evidence, client, "test-model") == draft

    calls = [call.kwargs for call in client.responses.parse.call_args_list]
    assert [call["text_format"] for call in calls] == [
        CampaignDraft,
        CampaignSemanticVerification,
        CampaignSemanticVerification,
    ]
    first, second = [json.loads(call["input"]) for call in calls[1:]]
    assert second.pop("correction_required")
    assert first == second


def test_campaign_fails_closed_if_verifier_retry_is_incomplete() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    incomplete = supported_verification(draft)
    incomplete.results.pop()
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=draft),
        MagicMock(output_parsed=incomplete),
        MagicMock(output_parsed=incomplete),
    ]

    with pytest.raises(CampaignVerificationResponseError, match="after retry"):
        generate_campaign_draft(evidence, client, "test-model")

    assert client.responses.parse.call_count == 3


def test_generate_campaign_retries_invalid_customer_copy() -> None:
    evidence = make_evidence()
    invalid_draft = make_draft(evidence)
    invalid_draft.assets[
        0
    ].body = "Get the best headphones with a limited-time discount today."
    corrected_draft = make_draft(evidence)
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=invalid_draft),
        MagicMock(output_parsed=corrected_draft),
        MagicMock(output_parsed=supported_verification(corrected_draft)),
    ]

    result = generate_campaign_draft(evidence, client, "test-model")

    assert result == corrected_draft
    assert client.responses.parse.call_count == 3
    retry_input = client.responses.parse.call_args_list[1].kwargs["input"]
    assert "unsupported absolute claim" in retry_input
    assert "Remove every contradicted assertion" in retry_input
