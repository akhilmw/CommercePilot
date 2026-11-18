from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from commercepilot.models.enums import ProductStatus


class ProductBase(BaseModel):
    sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    name: str = Field(min_length=2, max_length=255)
    category: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10)
    specifications: dict[str, Any] = Field(default_factory=dict)
    price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    status: ProductStatus = ProductStatus.ACTIVE

    @field_validator("sku", "currency", mode="before")
    @classmethod
    def uppercase_identifier(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name", "category", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, min_length=10)
    specifications: dict[str, Any] | None = None
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    status: ProductStatus | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
