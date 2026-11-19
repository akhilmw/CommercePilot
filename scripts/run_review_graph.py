from commercepilot.graph.review_graph import build_review_graph
from commercepilot.graph.review_state import ReviewAgentState


def main() -> None:
    review_graph = build_review_graph()
    initial_state = ReviewAgentState(
        product_sku="NOVA-AUDIO-001",
        evidence=None,
        insight=None,
        error=None,
    )

    result = review_graph.invoke(initial_state)
    if result["error"] is not None:
        raise RuntimeError(result["error"])

    evidence = result["evidence"]
    if evidence is None:
        raise RuntimeError("The review graph returned no evidence.")

    print("Review graph completed.")
    print(f"Product: {evidence.product_name} ({evidence.product_sku})")
    print(f"Reviews loaded: {evidence.review_count}")
    print(f"Average rating: {evidence.average_rating}")
    print(f"Rating distribution: {evidence.rating_distribution}")

    insight = result["insight"]
    if insight is None:
        raise RuntimeError("The review graph returned no insight.")

    print("\nReview Agent insight:")
    print(insight.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
