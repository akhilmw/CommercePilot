from enum import StrEnum


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PriceChangeType(StrEnum):
    INITIAL = "initial"
    DECREASED = "decreased"
    UNCHANGED = "unchanged"
    INCREASED = "increased"


class ReviewSentiment(StrEnum):
    POSITIVE = "positive"
    MIXED = "mixed"
    NEGATIVE = "negative"


class ImprovementPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompetitiveThreatLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(StrEnum):
    ANALYZE_REVIEWS = "analyze_reviews"
    MONITOR_COMPETITORS = "monitor_competitors"
    RECOMMEND_PRODUCT_IMPROVEMENT = "recommend_product_improvement"
    DRAFT_CATALOG_UPDATE = "draft_catalog_update"
    PUBLISH_CATALOG_UPDATE = "publish_catalog_update"
    DRAFT_CAMPAIGN = "draft_campaign"
    LAUNCH_CAMPAIGN = "launch_campaign"
    CHANGE_PRICE = "change_price"


class SourceAgent(StrEnum):
    REVIEW = "review_agent"
    COMPETITOR = "competitor_agent"
    ORCHESTRATOR = "orchestrator"
    CATALOG = "catalog_agent"
    CAMPAIGN = "campaign_agent"
