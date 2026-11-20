from openai import OpenAI

from commercepilot.core.config import get_settings
from commercepilot.graph.campaign_graph import build_campaign_graph
from commercepilot.graph.campaign_state import CampaignAgentState
from commercepilot.graph.competitor_graph import build_competitor_graph
from commercepilot.graph.competitor_state import CompetitorAgentState
from commercepilot.graph.review_graph import build_review_graph
from commercepilot.graph.review_state import ReviewAgentState
from commercepilot.services.strategy_synthesis import synthesize_strategy

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

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("COMMERCEPILOT_OPENAI_API_KEY is not configured.")
    strategy = synthesize_strategy(
        review_insight,
        competitor_insight,
        client=OpenAI(api_key=settings.openai_api_key),
        model=settings.openai_model,
    )

    campaign_result = build_campaign_graph().invoke(
        CampaignAgentState(
            product_sku=PRODUCT_SKU,
            review_insight=review_insight,
            competitor_insight=competitor_insight,
            strategy=strategy,
            evidence=None,
            draft=None,
            error=None,
        )
    )
    if campaign_result["error"] is not None:
        raise RuntimeError(campaign_result["error"])
    draft = campaign_result["draft"]
    if draft is None:
        raise RuntimeError("The Campaign Agent returned no draft.")

    print("Campaign graph completed.")
    print(f"Product: {draft.product_sku}")
    print("\nCampaign Agent draft:")
    print(draft.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
