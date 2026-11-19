from decimal import Decimal
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commercepilot.models.enums import (
    ActionType,
    ImprovementPriority,
    SourceAgent,
)


class PriceChangeParameters(BaseModel):
    sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    expected_current_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    new_price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10, max_length=750)
    rationale: str = Field(min_length=10, max_length=750)
    priority: ImprovementPriority
    source_agents: list[SourceAgent] = Field(min_length=1)
    evidence_ids: list[UUID] = Field(min_length=1)
    price_change: PriceChangeParameters | None = None

    @model_validator(mode="after")
    def validate_action_parameters(self) -> Self:
        is_price_change = self.action_type is ActionType.CHANGE_PRICE
        if is_price_change and self.price_change is None:
            raise ValueError("change_price requires structured price parameters")
        if not is_price_change and self.price_change is not None:
            raise ValueError(
                "price parameters are only valid for change_price"
            )
        return self


class GovernedAction(ActionProposal):
    action_id: UUID = Field(default_factory=uuid4)
    requires_human_approval: bool


class ApprovalPolicyResult(BaseModel):
    actions: list[GovernedAction]
    requires_human_approval: bool


class CommerceStrategy(BaseModel):
    product_sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    situation_summary: str = Field(min_length=20, max_length=1500)
    strategic_objectives: list[str] = Field(min_length=1)
    action_proposals: list[ActionProposal] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class HumanApprovalDecision(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=2, max_length=100)
    comment: str | None = Field(default=None, max_length=1000)
