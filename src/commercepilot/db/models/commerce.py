from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from commercepilot.db.base import Base
from commercepilot.models.enums import ProductStatus

if TYPE_CHECKING:
    from commercepilot.db.models.campaign import CampaignDraftRecord
    from commercepilot.db.models.catalog import CatalogDraftRecord


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        CheckConstraint(
            "catalog_version >= 1",
            name="ck_products_catalog_version",
        ),
        CheckConstraint(
            "jsonb_typeof(feature_bullets) = 'array'",
            name="ck_products_feature_bullets_array",
        ),
        CheckConstraint(
            "jsonb_typeof(seo_keywords) = 'array'",
            name="ck_products_seo_keywords_array",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        index=True,
    )
    description: Mapped[str] = mapped_column(Text)
    specifications: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        server_default="USD",
    )
    status: Mapped[ProductStatus] = mapped_column(
        SqlEnum(
            ProductStatus,
            name="product_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=ProductStatus.ACTIVE,
        server_default=ProductStatus.ACTIVE.value,
        index=True,
    )
    catalog_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
    )
    seo_title: Mapped[str | None] = mapped_column(String(70))
    meta_description: Mapped[str | None] = mapped_column(String(160))
    feature_bullets: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    seo_keywords: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    target_audience: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    reviews: Mapped[list[Review]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    competitor_products: Mapped[list[CompetitorProduct]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    catalog_drafts: Mapped[list[CatalogDraftRecord]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    campaign_drafts: Mapped[list[CampaignDraftRecord]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "rating BETWEEN 1 AND 5",
            name="ck_reviews_rating_range",
        ),
        UniqueConstraint(
            "source",
            "source_review_id",
            name="uq_reviews_source_review_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    source_review_id: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(
        String(50),
        default="novacart",
        server_default="novacart",
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    verified_purchase: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    product: Mapped[Product] = relationship(back_populates="reviews")


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    products: Mapped[list[CompetitorProduct]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CompetitorProduct(Base):
    __tablename__ = "competitor_products"
    __table_args__ = (
        UniqueConstraint(
            "competitor_id",
            "product_id",
            name="uq_competitor_products_competitor_product",
        ),
        UniqueConstraint(
            "competitor_id",
            "competitor_sku",
            name="uq_competitor_products_competitor_sku",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    competitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("competitors.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    competitor_sku: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    competitor: Mapped[Competitor] = relationship(back_populates="products")
    product: Mapped[Product] = relationship(
        back_populates="competitor_products",
    )
    price_snapshots: Mapped[list[CompetitorPriceSnapshot]] = relationship(
        back_populates="competitor_product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CompetitorPriceSnapshot.observed_at",
    )


class CompetitorPriceSnapshot(Base):
    __tablename__ = "competitor_price_snapshots"
    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="ck_competitor_price_snapshots_price_non_negative",
        ),
        UniqueConstraint(
            "competitor_product_id",
            "observed_at",
            name="uq_competitor_price_snapshots_product_observed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    competitor_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("competitor_products.id", ondelete="CASCADE"),
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        server_default="USD",
    )
    promotion: Mapped[str | None] = mapped_column(String(255))
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    competitor_product: Mapped[CompetitorProduct] = relationship(
        back_populates="price_snapshots",
    )
