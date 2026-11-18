from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import Competitor, CompetitorProduct, Product
from commercepilot.db.session import SessionLocal
from commercepilot.models.competitor import (
    CompetitorCreate,
    CompetitorProductCreate,
)
from commercepilot.models.product import ProductCreate
from commercepilot.services.market_simulation import MARKET_DAYS, insert_market_day

NOVA_SOUND_PRO = ProductCreate(
    sku="NOVA-AUDIO-001",
    name="NovaSound Pro",
    category="wireless-headphones",
    description=(
        "Wireless over-ear headphones with active noise cancellation, "
        "Bluetooth 5.3 connectivity, and up to 30 hours of battery life."
    ),
    specifications={
        "battery_hours": 30,
        "noise_cancellation": True,
        "bluetooth_version": "5.3",
        "weight_grams": 265,
        "colors": ["black", "silver", "navy"],
        "warranty_years": 1,
    },
    price=Decimal("129.99"),
    currency="USD",
)

COMPETITORS = (
    CompetitorCreate(name="AudioPeak", slug="audiopeak"),
    CompetitorCreate(name="SonicForge", slug="sonicforge"),
    CompetitorCreate(name="ClearWave", slug="clearwave"),
)

COMPETITOR_PRODUCTS = (
    {
        "competitor_slug": "audiopeak",
        "competitor_sku": "AP-CM2",
        "name": "ComfortMax 2",
        "description": "Wireless headphones positioned around long-session comfort.",
        "specifications": {
            "battery_hours": 35,
            "noise_cancellation": True,
            "weight_grams": 250,
        },
    },
    {
        "competitor_slug": "sonicforge",
        "competitor_sku": "SF-QCX",
        "name": "QuietCore X",
        "description": "Premium noise-cancelling wireless headphones.",
        "specifications": {
            "battery_hours": 32,
            "noise_cancellation": True,
            "weight_grams": 275,
        },
    },
    {
        "competitor_slug": "clearwave",
        "competitor_sku": "CW-SG",
        "name": "StudioGo",
        "description": "Portable wireless headphones for work and commuting.",
        "specifications": {
            "battery_hours": 28,
            "noise_cancellation": True,
            "weight_grams": 240,
        },
    },
)


def get_or_create_product(session: Session) -> Product:
    product = session.scalar(
        select(Product).where(Product.sku == NOVA_SOUND_PRO.sku)
    )
    if product is not None:
        return product

    product = Product(**NOVA_SOUND_PRO.model_dump())
    session.add(product)
    session.flush()
    print(f"Created product: {product.name}")
    return product


def get_or_create_competitors(session: Session) -> dict[str, Competitor]:
    competitors: dict[str, Competitor] = {}

    for competitor_data in COMPETITORS:
        competitor = session.scalar(
            select(Competitor).where(Competitor.slug == competitor_data.slug)
        )
        if competitor is None:
            competitor = Competitor(**competitor_data.model_dump())
            session.add(competitor)
            session.flush()
            print(f"Created competitor: {competitor.name}")

        competitors[competitor.slug] = competitor

    return competitors


def seed_competitor_products(
    session: Session,
    product: Product,
    competitors: dict[str, Competitor],
) -> None:
    for product_data in COMPETITOR_PRODUCTS:
        competitor = competitors[str(product_data["competitor_slug"])]
        competitor_sku = str(product_data["competitor_sku"])

        existing_product = session.scalar(
            select(CompetitorProduct).where(
                CompetitorProduct.competitor_id == competitor.id,
                CompetitorProduct.competitor_sku == competitor_sku,
            )
        )
        if existing_product is not None:
            continue

        competitor_product = CompetitorProductCreate(
            competitor_id=competitor.id,
            product_id=product.id,
            competitor_sku=competitor_sku,
            name=str(product_data["name"]),
            description=str(product_data["description"]),
            specifications=dict(product_data["specifications"]),
        )
        session.add(CompetitorProduct(**competitor_product.model_dump()))
        print(f"Created competitor product: {competitor_product.name}")


def seed_catalog() -> None:
    with SessionLocal() as session:
        product = get_or_create_product(session)
        competitors = get_or_create_competitors(session)
        seed_competitor_products(session, product, competitors)
        session.flush()

        created_snapshots = insert_market_day(session, MARKET_DAYS[0])
        session.commit()

        print(f"Day 1 price snapshots created: {created_snapshots}")
        print(f"Catalog ready for product: {product.name} ({product.sku})")


if __name__ == "__main__":
    seed_catalog()
