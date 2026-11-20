from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from commercepilot.mcp.client import (
    PublishCatalogUpdateResult,
    UpdateProductPriceResult,
)
from commercepilot.models.catalog import (
    CatalogComparison,
    CatalogDraft,
    CatalogFieldDiff,
)
from commercepilot.models.competitor import (
    CompetitiveRecommendation,
    CompetitorFinding,
    CompetitorInsight,
)
from commercepilot.models.enums import (
    ActionType,
    CatalogDraftStatus,
    CompetitiveThreatLevel,
    ImprovementPriority,
    ReviewSentiment,
    SourceAgent,
)
from commercepilot.models.orchestration import (
    ActionProposal,
    ApprovalPolicyResult,
    CommerceStrategy,
    GovernedAction,
    HumanApprovalDecision,
    PriceChangeParameters,
)
from commercepilot.models.review import (
    RequestedImprovement,
    ReviewInsight,
    ReviewTheme,
)

CHECKPOINT_TYPES = [
    ActionProposal,
    ActionType,
    ApprovalPolicyResult,
    CatalogComparison,
    CatalogDraft,
    CatalogDraftStatus,
    CatalogFieldDiff,
    CommerceStrategy,
    CompetitiveRecommendation,
    CompetitiveThreatLevel,
    CompetitorFinding,
    CompetitorInsight,
    GovernedAction,
    HumanApprovalDecision,
    ImprovementPriority,
    PriceChangeParameters,
    PublishCatalogUpdateResult,
    RequestedImprovement,
    ReviewInsight,
    ReviewSentiment,
    ReviewTheme,
    SourceAgent,
    UpdateProductPriceResult,
]


def build_orchestrator_checkpointer() -> InMemorySaver:
    return InMemorySaver(
        serde=JsonPlusSerializer(
            allowed_msgpack_modules=CHECKPOINT_TYPES,
        )
    )
