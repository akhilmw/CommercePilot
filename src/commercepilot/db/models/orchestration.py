from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from commercepilot.db.base import Base
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)

if TYPE_CHECKING:
    from commercepilot.db.models.commerce import Product


class OrchestrationRun(Base):
    __tablename__ = "orchestration_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(
        unique=True,
        index=True,
        default=uuid4,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[OrchestrationRunStatus] = mapped_column(
        SqlEnum(
            OrchestrationRunStatus,
            name="orchestration_run_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        default=OrchestrationRunStatus.PENDING,
        server_default=OrchestrationRunStatus.PENDING.value,
        index=True,
    )
    current_stage: Mapped[str | None] = mapped_column(String(64))
    force_catalog_update: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    force_campaign_update: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    product: Mapped[Product] = relationship(back_populates="orchestration_runs")
    approval_requests: Mapped[list[ApprovalRequest]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def product_sku(self) -> str:
        return self.product.sku

    @property
    def product_name(self) -> str:
        return self.product.name


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "interrupt_id",
            name="uq_approval_requests_run_interrupt",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("orchestration_runs.id", ondelete="CASCADE"),
        index=True,
    )
    interrupt_id: Mapped[str] = mapped_column(String(255))
    approval_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[ApprovalRequestStatus] = mapped_column(
        SqlEnum(
            ApprovalRequestStatus,
            name="approval_request_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            create_constraint=True,
        ),
        default=ApprovalRequestStatus.PENDING,
        server_default=ApprovalRequestStatus.PENDING.value,
        index=True,
    )
    reviewer: Mapped[str | None] = mapped_column(String(100))
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    run: Mapped[OrchestrationRun] = relationship(back_populates="approval_requests")
