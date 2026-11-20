from commercepilot.graph.catalog_graph import build_catalog_graph
from commercepilot.graph.catalog_state import CatalogAgentState
from commercepilot.graph.competitor_graph import build_competitor_graph
from commercepilot.graph.competitor_state import CompetitorAgentState
from commercepilot.graph.review_graph import build_review_graph
from commercepilot.graph.review_state import ReviewAgentState

PRODUCT_SKU = "NOVA-AUDIO-001"


def main() -> None:
    review_result = build_review_graph().invoke(
        ReviewAgentState(
            product_sku=PRODUCT_SKU,
            evidence=None,
            insight=None,
            error=None,
        )
    )
    if review_result["error"] is not None:
        raise RuntimeError(review_result["error"])
    review_insight = review_result["insight"]
    if review_insight is None:
        raise RuntimeError("The Review Agent returned no insight.")

    competitor_result = build_competitor_graph().invoke(
        CompetitorAgentState(
            product_sku=PRODUCT_SKU,
            evidence=None,
            insight=None,
            error=None,
        )
    )
    if competitor_result["error"] is not None:
        raise RuntimeError(competitor_result["error"])
    competitor_insight = competitor_result["insight"]
    if competitor_insight is None:
        raise RuntimeError("The Competitor Agent returned no insight.")

    catalog_result = build_catalog_graph().invoke(
        CatalogAgentState(
            product_sku=PRODUCT_SKU,
            review_insight=review_insight,
            competitor_insight=competitor_insight,
            evidence=None,
            draft=None,
            error=None,
        )
    )
    if catalog_result["error"] is not None:
        raise RuntimeError(catalog_result["error"])
    draft = catalog_result["draft"]
    if draft is None:
        raise RuntimeError("The Catalog Agent returned no draft.")

    print("Catalog graph completed.")
    print(f"Product: {draft.product_sku}")
    print("\nCatalog Agent draft:")
    print(draft.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
