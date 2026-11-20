from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import Product
from commercepilot.models.catalog import CatalogEvidenceSet
from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.product import ProductRead
from commercepilot.models.review import ReviewInsight


def load_catalog_evidence(
    session: Session,
    product_sku: str,
    review_insight: ReviewInsight,
    competitor_insight: CompetitorInsight,
) -> CatalogEvidenceSet:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise ValueError(f"Unknown product SKU: {product_sku}")

    return CatalogEvidenceSet(
        product=ProductRead.model_validate(product),
        review_insight=review_insight,
        competitor_insight=competitor_insight,
    )
