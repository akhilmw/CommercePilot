from decimal import Decimal

import pytest
from pydantic import ValidationError

from commercepilot.models.enums import ProductStatus
from commercepilot.models.product import ProductCreate


def build_product(**overrides: object) -> ProductCreate:
    values: dict[str, object] = {
        "sku": "NOVA-AUDIO-001",
        "name": "NovaSound Pro",
        "category": "wireless-headphones",
        "description": "Wireless headphones with active noise cancellation.",
        "price": Decimal("129.99"),
    }
    values.update(overrides)
    return ProductCreate.model_validate(values)


def test_product_create_normalizes_identifiers_and_text() -> None:
    product = build_product(
        sku="nova-audio-001",
        name="  NovaSound Pro  ",
        currency="usd",
    )

    assert product.sku == "NOVA-AUDIO-001"
    assert product.name == "NovaSound Pro"
    assert product.currency == "USD"
    assert product.status is ProductStatus.ACTIVE


def test_product_create_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        build_product(price=Decimal("-0.01"))


def test_product_create_rejects_invalid_sku() -> None:
    with pytest.raises(ValidationError):
        build_product(sku="invalid sku")
