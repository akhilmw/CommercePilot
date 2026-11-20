from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from commercepilot.db.base import Base
from commercepilot.models.enums import CatalogDraftStatus

if TYPE_CHECKING:
    from commercepilot.db.models.commerce import Product


class CatalogDraftRecord(Base):
    __tablename__ = "catalog_drafts"
    __table_args__ = (
        CheckConstraint(
            "expected_catalog_version >= 1",
            name="ck_catalog_drafts_expected_version",
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_catalog_drafts_confidence_range",
        ),
        CheckConstraint(
            "jsonb_typeof(feature_bullets) = 'array'",
            name="ck_catalog_drafts_feature_bullets_array",
        ),
        CheckConstraint(
            "jsonb_typeof(seo_keywords) = 'array'",
            name="ck_catalog_drafts_seo_keywords_array",
        ),
        CheckConstraint(
            "jsonb_typeof(supporting_evidence_ids) = 'array'",
            name="ck_catalog_drafts_evidence_ids_array",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    expected_catalog_version: Mapped[int] = mapped_column(Integer)
    seo_title: Mapped[str] = mapped_column(String(70))
    meta_description: Mapped[str] = mapped_column(String(160))
    product_description: Mapped[str] = mapped_column(Text)
    feature_bullets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    seo_keywords: Mapped[list[str]] = mapped_column(JSONB)
    target_audience: Mapped[str] = mapped_column(String(300))
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    status: Mapped[CatalogDraftStatus] = mapped_column(
        SqlEnum(
            CatalogDraftStatus,
            name="catalog_draft_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        default=CatalogDraftStatus.DRAFT,
        server_default=CatalogDraftStatus.DRAFT.value,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    product: Mapped[Product] = relationship(back_populates="catalog_drafts")
