from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from commercepilot.models.enums import ActionType, CampaignChannel


class EvaluationTarget(StrEnum):
    REVIEW_AGENT = "review_agent"
    COMPETITOR_AGENT = "competitor_agent"
    STRATEGY = "strategy"
    CATALOG_AGENT = "catalog_agent"
    CAMPAIGN_AGENT = "campaign_agent"
    GOVERNANCE = "governance"


class EvaluationCase(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$", min_length=3, max_length=80)
    name: str = Field(min_length=5, max_length=160)
    target: EvaluationTarget
    product_sku: str | None = Field(
        default=None,
        pattern=r"^[A-Z0-9-]+$",
    )
    required_topic_groups: list[list[str]] = Field(default_factory=list)
    expected_competitors: list[str] = Field(default_factory=list)
    expected_price_drop_competitors: list[str] = Field(default_factory=list)
    proposed_action_types: list[ActionType] = Field(default_factory=list)
    forbidden_action_types: list[ActionType] = Field(default_factory=list)
    minimum_action_count: int = Field(default=1, ge=0)
    expected_channels: list[CampaignChannel] = Field(default_factory=list)
    force_catalog_update: bool = False
    force_campaign_update: bool = False
    expected_route: str | None = None
    allowed_routes: list[str] = Field(default_factory=list)
    expected_human_approval: bool | None = None

    @model_validator(mode="after")
    def validate_target_inputs(self) -> "EvaluationCase":
        if self.target is not EvaluationTarget.GOVERNANCE and self.product_sku is None:
            raise ValueError("Agent evaluation cases require a product SKU.")
        if self.target is EvaluationTarget.GOVERNANCE:
            if not self.proposed_action_types:
                raise ValueError("Governance cases require proposed action types.")
            if self.expected_route is None:
                raise ValueError("Governance cases require an expected route.")
            if self.expected_human_approval is None:
                raise ValueError(
                    "Governance cases require an approval expectation."
                )
        return self


class EvaluationCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class EvaluationCaseResult(BaseModel):
    case_id: str
    case_name: str
    target: EvaluationTarget
    product_sku: str | None
    passed: bool
    latency_ms: float = Field(ge=0)
    checks: list[EvaluationCheck]
    error: str | None = None


class EvaluationReport(BaseModel):
    generated_at: datetime
    model: str
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)
    results: list[EvaluationCaseResult]
