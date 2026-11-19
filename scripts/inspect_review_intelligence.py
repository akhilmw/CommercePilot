from commercepilot.db.session import SessionLocal
from commercepilot.services.review_intelligence import load_review_evidence


def main() -> None:
    with SessionLocal() as session:
        evidence = load_review_evidence(session, "NOVA-AUDIO-001")

    print(f"Product: {evidence.product_name} ({evidence.product_sku})")
    print(f"Reviews: {evidence.review_count}")
    print(f"Average rating: {evidence.average_rating}")
    print(f"Rating distribution: {evidence.rating_distribution}")
    print(f"Verified purchases: {evidence.verified_purchase_count}")
    print(f"Review window: {evidence.reviewed_from} -> {evidence.reviewed_to}")

    print("\nEvidence:")
    for review in evidence.reviews:
        print(f"- [{review.rating}/5] {review.title}: {review.body}")


if __name__ == "__main__":
    main()
