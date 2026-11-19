from commercepilot.graph.competitor_graph import build_competitor_graph
from commercepilot.graph.competitor_state import CompetitorAgentState


def main() -> None:
    competitor_graph = build_competitor_graph()
    initial_state = CompetitorAgentState(
        product_sku="NOVA-AUDIO-001",
        evidence=None,
        insight=None,
        error=None,
    )

    result = competitor_graph.invoke(initial_state)
    if result["error"] is not None:
        raise RuntimeError(result["error"])

    evidence = result["evidence"]
    insight = result["insight"]
    if evidence is None or insight is None:
        raise RuntimeError("The competitor graph returned an incomplete result.")

    print("Competitor graph completed.")
    print(f"Product: {evidence.product_name} ({evidence.product_sku})")
    print(f"Our price: {evidence.currency} {evidence.our_price}")
    print(f"Competitors analyzed: {len(evidence.price_changes)}")
    print("\nCompetitor Agent insight:")
    print(insight.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
