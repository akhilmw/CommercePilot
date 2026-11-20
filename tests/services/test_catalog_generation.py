from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from commercepilot.models.catalog import (
    CatalogBullet,
    CatalogClaimVerification,
    CatalogDraft,
    CatalogEvidenceSet,
    CatalogSemanticVerification,
)
from commercepilot.models.competitor import CompetitorFinding, CompetitorInsight
from commercepilot.models.enums import (
    CompetitiveThreatLevel,
    ProductStatus,
    ReviewSentiment,
)
from commercepilot.models.product import ProductRead
from commercepilot.models.review import ReviewInsight, ReviewTheme
from commercepilot.services.catalog_generation import (
    generate_catalog_draft,
    normalize_catalog_copy,
    validate_catalog_copy_quality,
    validate_catalog_draft,
    verify_catalog_draft_semantics,
)


def make_evidence() -> CatalogEvidenceSet:
    product_id = uuid4()
    review_id = uuid4()
    snapshot_id = uuid4()
    timestamp = datetime(2026, 11, 19, tzinfo=UTC)
    return CatalogEvidenceSet(
        product=ProductRead(
            id=product_id,
            sku="NOVA-AUDIO-001",
            name="NovaSound Pro",
            category="wireless-headphones",
            description=(
                "Wireless headphones with 40-hour battery life for focused "
                "everyday listening."
            ),
            specifications={"battery_life_hours": 40},
            price=Decimal("109.99"),
            currency="USD",
            status=ProductStatus.ACTIVE,
            catalog_version=1,
            created_at=timestamp,
            updated_at=timestamp,
        ),
        review_insight=ReviewInsight(
            product_sku="NOVA-AUDIO-001",
            overall_sentiment=ReviewSentiment.POSITIVE,
            executive_summary=(
                "Customers consistently value battery life and audio quality."
            ),
            strengths=[
                ReviewTheme(
                    theme="Battery life",
                    summary="Customers praise the long battery performance.",
                    evidence_review_ids=[review_id],
                )
            ],
            complaints=[],
            requested_improvements=[],
            confidence=0.91,
        ),
        competitor_insight=CompetitorInsight(
            product_sku="NOVA-AUDIO-001",
            our_price=Decimal("109.99"),
            currency="USD",
            overall_threat_level=CompetitiveThreatLevel.HIGH,
            market_summary=("The category has significant promotional price pressure."),
            findings=[
                CompetitorFinding(
                    competitor_product_id=uuid4(),
                    competitor_name="AudioPeak",
                    threat_level=CompetitiveThreatLevel.HIGH,
                    summary="AudioPeak is running a temporary promotion.",
                    evidence_snapshot_ids=[snapshot_id],
                )
            ],
            recommended_actions=[],
            confidence=0.88,
        ),
    )


def make_draft(evidence: CatalogEvidenceSet) -> CatalogDraft:
    review_id = evidence.review_insight.strengths[0].evidence_review_ids[0]
    product_id = evidence.product.id
    return CatalogDraft(
        product_sku=evidence.product.sku,
        seo_title="NovaSound Pro Wireless Noise-Cancelling Headphones",
        meta_description=(
            "Enjoy focused wireless listening with detailed sound and a "
            "40-hour battery designed for commutes and productive workdays."
        ),
        product_description=(
            "NovaSound Pro combines detailed wireless audio with a 40-hour "
            "battery in a versatile over-ear design. It is positioned for "
            "commuters and professionals seeking dependable everyday listening."
        ),
        feature_bullets=[
            CatalogBullet(
                text="A 40-hour battery supports extended listening sessions.",
                evidence_ids=[product_id],
            ),
            CatalogBullet(
                text="Customers consistently praise the long battery life.",
                evidence_ids=[review_id],
            ),
            CatalogBullet(
                text="Detailed wireless audio supports everyday listening.",
                evidence_ids=[product_id, review_id],
            ),
        ],
        seo_keywords=[
            "wireless headphones",
            "40-hour battery headphones",
            "commuter headphones",
        ],
        target_audience=(
            "Commuters and professionals seeking dependable wireless listening."
        ),
        supporting_evidence_ids=[product_id, review_id],
        confidence=0.87,
    )


def test_generate_catalog_draft_returns_validated_structured_output() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    client = MagicMock()
    verification = supported_verification(draft)
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=draft),
        MagicMock(output_parsed=verification),
    ]

    result = generate_catalog_draft(evidence, client, "test-model")

    assert result == draft
    request = client.responses.parse.call_args_list[0].kwargs
    assert request["model"] == "test-model"
    assert request["text_format"] is CatalogDraft


def supported_verification(draft: CatalogDraft) -> CatalogSemanticVerification:
    claim_ids = [
        "seo_title",
        "meta_description",
        "product_description",
        *[f"feature_bullet_{index}" for index in range(len(draft.feature_bullets))],
        "seo_keywords",
        "target_audience",
    ]
    return CatalogSemanticVerification(
        results=[
            CatalogClaimVerification(
                claim_id=claim_id,
                supported=True,
                rationale="The cited evidence directly supports this claim.",
            )
            for claim_id in claim_ids
        ]
    )


def test_semantic_verifier_rejects_unsupported_padded_earcups_claim() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.feature_bullets[
        0
    ].text = "Padded earcups provide lasting comfort for long listening sessions."
    verification = supported_verification(draft)
    verification.results[3] = CatalogClaimVerification(
        claim_id="feature_bullet_0",
        supported=False,
        rationale=(
            "The cited product record does not mention padded earcups or comfort."
        ),
    )
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = verification

    with pytest.raises(
        ValueError,
        match="feature_bullet_0.*does not mention padded earcups",
    ):
        verify_catalog_draft_semantics(
            draft,
            evidence,
            client,
            "test-model",
        )


def test_semantic_verifier_requires_exactly_one_result_per_claim() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    verification = supported_verification(draft)
    verification.results.pop()
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = verification

    with pytest.raises(ValueError, match="exactly the requested claim IDs"):
        verify_catalog_draft_semantics(
            draft,
            evidence,
            client,
            "test-model",
        )


def test_validate_catalog_draft_rejects_unknown_evidence() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.feature_bullets[0].evidence_ids = [uuid4()]

    with pytest.raises(ValueError, match="unknown evidence IDs"):
        validate_catalog_draft(draft, evidence)


def test_validate_catalog_draft_requires_product_record_citation() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    review_id = evidence.review_insight.strengths[0].evidence_review_ids[0]
    draft.supporting_evidence_ids = [review_id]

    with pytest.raises(ValueError, match="must cite the product record"):
        validate_catalog_draft(draft, evidence)


def test_validate_catalog_draft_rejects_unsupported_numeric_claim() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.feature_bullets[
        0
    ].text = "An 80-hour battery supports extended listening sessions."

    with pytest.raises(ValueError, match="unsupported numeric claims: 80"):
        validate_catalog_draft(draft, evidence)


def test_validate_catalog_draft_rejects_absolute_claim() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.seo_title = "NovaSound Pro Best Wireless Headphones"

    with pytest.raises(ValueError, match="unsupported absolute claim: best"):
        validate_catalog_draft(draft, evidence)


def test_validate_catalog_draft_rejects_bullet_missing_from_supporting_ids() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    snapshot_id: UUID = evidence.competitor_insight.findings[0].evidence_snapshot_ids[0]
    draft.feature_bullets[0].evidence_ids = [snapshot_id]

    with pytest.raises(ValueError, match="missing from supporting evidence"):
        validate_catalog_draft(draft, evidence)


def test_catalog_quality_rejects_corrupted_mixed_script_copy() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.meta_description = (
        "Enjoy detailed wireless sound and dependable battery life for "
        "productive workdays and everyday listening a長."
    )

    with pytest.raises(ValueError, match="non-Latin characters.*長"):
        validate_catalog_copy_quality(draft, evidence)


def test_catalog_quality_rejects_incomplete_copy() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.meta_description = draft.meta_description.removesuffix(".")

    with pytest.raises(ValueError, match="meta_description"):
        validate_catalog_copy_quality(draft, evidence)


def test_catalog_copy_normalization_completes_sentences() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.meta_description = draft.meta_description.removesuffix(".")
    draft.product_description = draft.product_description.removesuffix(".")
    draft.feature_bullets[0].text = draft.feature_bullets[0].text.removesuffix(".")
    draft.target_audience = draft.target_audience.removesuffix(".")

    normalized = normalize_catalog_copy(draft)

    assert normalized.meta_description.endswith(".")
    assert normalized.product_description.endswith(".")
    assert normalized.feature_bullets[0].text.endswith(".")
    assert normalized.target_audience.endswith(".")


def test_catalog_copy_normalization_preserves_last_complete_sentence() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.meta_description = (
        "NovaSound Pro wireless headphones feature detailed audio and a "
        "40-hour battery for everyday listening. Reviewers note that customers "
        "appreciate the balanced sound during commutes and productive workdays"
    )

    normalized = normalize_catalog_copy(draft)

    assert normalized.meta_description == (
        "NovaSound Pro wireless headphones feature detailed audio and a "
        "40-hour battery for everyday listening."
    )


def test_catalog_quality_rejects_dangling_attribution_phrase() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.meta_description = (
        "NovaSound Pro wireless headphones deliver dependable listening for "
        "commutes and productive workdays. Reviewers note."
    )

    with pytest.raises(ValueError, match="dangling attribution.*meta_description"):
        validate_catalog_copy_quality(draft, evidence)


def test_generate_catalog_draft_normalizes_missing_terminal_punctuation() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    draft.meta_description = draft.meta_description.removesuffix(".")
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=draft),
        MagicMock(output_parsed=supported_verification(draft)),
    ]

    result = generate_catalog_draft(evidence, client, "test-model")

    assert result.meta_description.endswith(".")
    assert client.responses.parse.call_count == 2


def test_catalog_quality_rejects_competitor_content_in_feature_bullet() -> None:
    evidence = make_evidence()
    draft = make_draft(evidence)
    snapshot_id = evidence.competitor_insight.findings[0].evidence_snapshot_ids[0]
    draft.feature_bullets[0] = CatalogBullet(
        text=(
            "AudioPeak is running a promotion, so monitor competitor price activity."
        ),
        evidence_ids=[snapshot_id],
    )

    with pytest.raises(ValueError, match="competitor-facing content"):
        validate_catalog_copy_quality(draft, evidence)


def test_generate_catalog_draft_retries_failed_quality_gate() -> None:
    evidence = make_evidence()
    invalid_draft = make_draft(evidence)
    invalid_draft.meta_description = (
        "Enjoy detailed wireless sound and dependable battery life for "
        "productive workdays and everyday listening a長."
    )
    corrected_draft = make_draft(evidence)
    verification = supported_verification(corrected_draft)
    client = MagicMock()
    client.responses.parse.side_effect = [
        MagicMock(output_parsed=invalid_draft),
        MagicMock(output_parsed=corrected_draft),
        MagicMock(output_parsed=verification),
    ]

    result = generate_catalog_draft(evidence, client, "test-model")

    assert result == corrected_draft
    assert client.responses.parse.call_count == 3
    retry_input = client.responses.parse.call_args_list[1].kwargs["input"]
    assert "unexpected non-Latin characters" in retry_input
