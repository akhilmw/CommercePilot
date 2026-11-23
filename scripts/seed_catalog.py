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

NOVA_FIT_WATCH = ProductCreate(
    sku="NOVA-WEAR-001",
    name="NovaFit Watch",
    category="smartwatches",
    description=(
        "GPS smartwatch with heart-rate and sleep tracking, a bright AMOLED "
        "display, and up to seven days of battery life."
    ),
    specifications={
        "battery_days": 7,
        "display": "1.4-inch AMOLED",
        "gps": True,
        "water_resistance_atm": 5,
        "health_tracking": ["heart_rate", "sleep", "blood_oxygen"],
        "colors": ["midnight", "silver", "rose"],
        "warranty_years": 1,
    },
    price=Decimal("249.99"),
    currency="USD",
)

NOVA_BREW_PRO = ProductCreate(
    sku="NOVA-HOME-001",
    name="NovaBrew Pro",
    category="espresso-machines",
    description=(
        "Compact semi-automatic espresso machine with a 15-bar pump, "
        "thermoblock heating, and an integrated steam wand."
    ),
    specifications={
        "pump_pressure_bar": 15,
        "heating_system": "thermoblock",
        "water_tank_liters": 1.5,
        "steam_wand": True,
        "cup_sizes": ["single", "double"],
        "finish": ["stainless steel", "matte black"],
        "warranty_years": 2,
    },
    price=Decimal("179.99"),
    currency="USD",
)

PRODUCTS = (NOVA_SOUND_PRO, NOVA_FIT_WATCH, NOVA_BREW_PRO)

COMPETITORS = (
    CompetitorCreate(name="AudioPeak", slug="audiopeak"),
    CompetitorCreate(name="SonicForge", slug="sonicforge"),
    CompetitorCreate(name="ClearWave", slug="clearwave"),
    CompetitorCreate(name="PulseLabs", slug="pulselabs"),
    CompetitorCreate(name="Kinetic", slug="kinetic"),
    CompetitorCreate(name="WellSync", slug="wellsync"),
    CompetitorCreate(name="BrewCraft", slug="brewcraft"),
    CompetitorCreate(name="CafeWorks", slug="cafeworks"),
    CompetitorCreate(name="BeanForge", slug="beanforge"),
)

COMPETITOR_PRODUCTS = (
    {
        "product_sku": "NOVA-AUDIO-001",
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
        "product_sku": "NOVA-AUDIO-001",
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
        "product_sku": "NOVA-AUDIO-001",
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
    {
        "product_sku": "NOVA-WEAR-001",
        "competitor_slug": "pulselabs",
        "competitor_sku": "PL-PT4",
        "name": "PulseTrack V4",
        "description": "Fitness smartwatch focused on training and recovery.",
        "specifications": {
            "battery_days": 6,
            "display": "AMOLED",
            "gps": True,
            "water_resistance_atm": 5,
        },
    },
    {
        "product_sku": "NOVA-WEAR-001",
        "competitor_slug": "kinetic",
        "competitor_sku": "KN-MOS",
        "name": "MotionOne S",
        "description": "Premium everyday smartwatch with advanced health sensors.",
        "specifications": {
            "battery_days": 5,
            "display": "AMOLED",
            "gps": True,
            "water_resistance_atm": 5,
        },
    },
    {
        "product_sku": "NOVA-WEAR-001",
        "competitor_slug": "wellsync",
        "competitor_sku": "WS-VBP",
        "name": "VitalBand Pro",
        "description": "Lightweight health and activity tracking smartwatch.",
        "specifications": {
            "battery_days": 8,
            "display": "OLED",
            "gps": True,
            "water_resistance_atm": 5,
        },
    },
    {
        "product_sku": "NOVA-HOME-001",
        "competitor_slug": "brewcraft",
        "competitor_sku": "BC-BH",
        "name": "Barista Home",
        "description": "Semi-automatic home espresso machine with steam wand.",
        "specifications": {
            "pump_pressure_bar": 15,
            "water_tank_liters": 1.7,
            "steam_wand": True,
        },
    },
    {
        "product_sku": "NOVA-HOME-001",
        "competitor_slug": "cafeworks",
        "competitor_sku": "CFW-CT",
        "name": "CremaTouch",
        "description": "Compact espresso machine for small kitchens.",
        "specifications": {
            "pump_pressure_bar": 15,
            "water_tank_liters": 1.3,
            "steam_wand": True,
        },
    },
    {
        "product_sku": "NOVA-HOME-001",
        "competitor_slug": "beanforge",
        "competitor_sku": "BF-MP",
        "name": "MorningPro",
        "description": "Entry-level espresso maker with rapid heating.",
        "specifications": {
            "pump_pressure_bar": 15,
            "water_tank_liters": 1.4,
            "steam_wand": True,
        },
    },
)


def get_or_create_products(session: Session) -> dict[str, Product]:
    products: dict[str, Product] = {}
    for product_data in PRODUCTS:
        product = session.scalar(
            select(Product).where(Product.sku == product_data.sku)
        )
        if product is None:
            product = Product(**product_data.model_dump())
            session.add(product)
            session.flush()
            print(f"Created product: {product.name}")
        products[product.sku] = product
    return products


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
    products: dict[str, Product],
    competitors: dict[str, Competitor],
) -> None:
    for product_data in COMPETITOR_PRODUCTS:
        product = products[str(product_data["product_sku"])]
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
        products = get_or_create_products(session)
        competitors = get_or_create_competitors(session)
        seed_competitor_products(session, products, competitors)
        session.flush()

        created_snapshots = sum(
            insert_market_day(session, market_day)
            for market_day in MARKET_DAYS[:2]
        )
        session.commit()

        print(f"Initial price snapshots created: {created_snapshots}")
        for product in products.values():
            print(f"Catalog ready for product: {product.name} ({product.sku})")


if __name__ == "__main__":
    seed_catalog()
