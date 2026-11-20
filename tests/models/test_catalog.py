from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.catalog import CatalogBullet, CatalogDraft


def make_draft() -> CatalogDraft:
    evidence_ids = [uuid4(), uuid4(), uuid4()]
    return CatalogDraft(
        product_sku="NOVA-AUDIO-001",
        seo_title="NovaSound Pro Wireless Noise-Cancelling Headphones",
        meta_description=(
            "Experience long-lasting wireless listening with powerful sound "
            "and effective noise cancellation for commutes and focused work."
        ),
        product_description=(
            "NovaSound Pro combines detailed wireless audio, long battery "
            "life, and effective noise cancellation in a versatile design "
            "for commuters, focused professionals, and everyday listeners."
        ),
        feature_bullets=[
            CatalogBullet(
                text="Long battery life supports extended listening sessions.",
                evidence_ids=[evidence_ids[0]],
            ),
            CatalogBullet(
                text="Effective noise cancellation helps reduce distractions.",
                evidence_ids=[evidence_ids[1]],
            ),
            CatalogBullet(
                text="Detailed audio reproduction suits music and media.",
                evidence_ids=[evidence_ids[2]],
            ),
        ],
        seo_keywords=[
            "wireless headphones",
            "noise cancelling headphones",
            "long battery headphones",
        ],
        target_audience="Commuters and professionals seeking focused listening.",
        supporting_evidence_ids=evidence_ids,
        confidence=0.86,
    )


def test_catalog_draft_accepts_evidence_backed_content() -> None:
    draft = make_draft()

    assert draft.product_sku == "NOVA-AUDIO-001"
    assert len(draft.feature_bullets) == 3
    assert draft.confidence == 0.86


def test_catalog_bullet_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        CatalogBullet(
            text="Long battery life supports extended listening sessions.",
            evidence_ids=[],
        )


def test_catalog_draft_requires_at_least_three_bullets() -> None:
    payload = make_draft().model_dump()
    payload["feature_bullets"] = payload["feature_bullets"][:2]

    with pytest.raises(ValidationError):
        CatalogDraft.model_validate(payload)


def test_catalog_draft_rejects_unknown_fields() -> None:
    payload = make_draft().model_dump()
    payload["unreviewed_claim"] = "Best headphones in the world"

    with pytest.raises(ValidationError):
        CatalogDraft.model_validate(payload)
