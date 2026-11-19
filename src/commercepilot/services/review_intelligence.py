from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import Product, Review
from commercepilot.models.review import ReviewEvidenceSet, ReviewRead


def load_review_evidence(
    session: Session,
    product_sku: str,
) -> ReviewEvidenceSet:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise ValueError(f"Unknown product SKU: {product_sku}")

    review_records = list(
        session.scalars(
            select(Review)
            .where(Review.product_id == product.id)
            .order_by(Review.reviewed_at)
        ).all()
    )
    reviews = [ReviewRead.model_validate(review) for review in review_records]

    rating_distribution = {rating: 0 for rating in range(1, 6)}
    for review in reviews:
        rating_distribution[review.rating] += 1

    review_count = len(reviews)
    average_rating = (
        round(sum(review.rating for review in reviews) / review_count, 2)
        if review_count
        else 0.0
    )

    return ReviewEvidenceSet(
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        review_count=review_count,
        average_rating=average_rating,
        rating_distribution=rating_distribution,
        verified_purchase_count=sum(
            review.verified_purchase for review in reviews
        ),
        reviewed_from=reviews[0].reviewed_at if reviews else None,
        reviewed_to=reviews[-1].reviewed_at if reviews else None,
        reviews=reviews,
    )
