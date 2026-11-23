from collections import Counter

from commercepilot.services.market_simulation import MARKET_DAYS
from scripts.seed_catalog import COMPETITOR_PRODUCTS, PRODUCTS


def test_seed_catalog_contains_three_unique_products() -> None:
    assert {product.sku for product in PRODUCTS} == {
        "NOVA-AUDIO-001",
        "NOVA-WEAR-001",
        "NOVA-HOME-001",
    }


def test_each_product_has_three_competitor_mappings() -> None:
    counts = Counter(
        str(competitor_product["product_sku"])
        for competitor_product in COMPETITOR_PRODUCTS
    )
    assert counts == {
        "NOVA-AUDIO-001": 3,
        "NOVA-WEAR-001": 3,
        "NOVA-HOME-001": 3,
    }


def test_every_market_day_covers_every_competitor_product() -> None:
    expected_skus = {
        str(competitor_product["competitor_sku"])
        for competitor_product in COMPETITOR_PRODUCTS
    }
    for market_day in MARKET_DAYS:
        assert {price.competitor_sku for price in market_day.prices} == expected_skus
