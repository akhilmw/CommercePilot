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
from commercepilot.models.enums import CampaignDraftStatus

if TYPE_CHECKING:
    from commercepilot.db.models.commerce import Product


class CampaignDraftRecord(Base):
    __tablename__ = "campaign_drafts"
    __table_args__ = (
        CheckConstraint(
            "source_catalog_version >= 1",
            name="ck_campaign_drafts_catalog_version",
        ),
        CheckConstraint(
            "source_price >= 0",
            name="ck_campaign_drafts_source_price",
        ),
        CheckConstraint(
            "duration_days BETWEEN 1 AND 90",
            name="ck_campaign_drafts_duration_days",
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_campaign_drafts_confidence_range",
        ),
        CheckConstraint(
            "jsonb_typeof(assets) = 'array'",
            name="ck_campaign_drafts_assets_array",
        ),
        CheckConstraint(
            "jsonb_typeof(success_metrics) = 'array'",
            name="ck_campaign_drafts_metrics_array",
        ),
        CheckConstraint(
            "jsonb_typeof(supporting_evidence_ids) = 'array'",
            name="ck_campaign_drafts_evidence_ids_array",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    source_catalog_version: Mapped[int] = mapped_column(Integer)
    source_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    name: Mapped[str] = mapped_column(String(120))
    objective: Mapped[str] = mapped_column(String(500))
    target_audience: Mapped[str] = mapped_column(String(500))
    core_message: Mapped[str] = mapped_column(Text)
    assets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    duration_days: Mapped[int] = mapped_column(Integer)
    success_metrics: Mapped[list[str]] = mapped_column(JSONB)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    status: Mapped[CampaignDraftStatus] = mapped_column(
        SqlEnum(
            CampaignDraftStatus,
            name="campaign_draft_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        default=CampaignDraftStatus.DRAFT,
        server_default=CampaignDraftStatus.DRAFT.value,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

    product: Mapped[Product] = relationship(back_populates="campaign_drafts")
