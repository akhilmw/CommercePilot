from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import Product, Review
from commercepilot.models.review import ReviewCreate, ReviewIngestionResult


def ingest_reviews(
    session: Session,
    product_sku: str,
    reviews: Sequence[ReviewCreate],
) -> ReviewIngestionResult:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise ValueError(f"Unknown product SKU: {product_sku}")

    created = 0
    skipped = 0

    for review_data in reviews:
        existing_review = session.scalar(
            select(Review).where(
                Review.source == review_data.source,
                Review.source_review_id == review_data.source_review_id,
            )
        )
        if existing_review is not None:
            skipped += 1
            continue

        session.add(
            Review(
                product_id=product.id,
                **review_data.model_dump(),
            )
        )
        created += 1

    session.flush()

    return ReviewIngestionResult(
        product_sku=product_sku,
        received=len(reviews),
        created=created,
        skipped=skipped,
    )
