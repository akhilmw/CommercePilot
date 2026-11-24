from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import cast
from uuid import UUID, uuid4

from openai import OpenAI
from sqlalchemy import select

from commercepilot.core.config import get_settings
from commercepilot.db.models import Product
from commercepilot.db.session import SessionLocal
from commercepilot.evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationCheck,
    EvaluationReport,
    EvaluationTarget,
)
from commercepilot.graph.orchestrator_graph import route_after_synthesis
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.models.campaign import CampaignDraft, CampaignEvidenceSet
from commercepilot.models.catalog import CatalogDraft, CatalogEvidenceSet
from commercepilot.models.competitor import CompetitorEvidenceSet, CompetitorInsight
from commercepilot.models.enums import ActionType, ImprovementPriority, SourceAgent
from commercepilot.models.orchestration import (
    ActionProposal,
    CommerceStrategy,
    PriceChangeParameters,
)
from commercepilot.models.product import ProductRead
from commercepilot.models.review import ReviewEvidenceSet, ReviewInsight
from commercepilot.services.approval_policy import apply_approval_policy
from commercepilot.services.campaign_generation import generate_campaign_draft
from commercepilot.services.catalog_generation import generate_catalog_draft
from commercepilot.services.catalog_intelligence import load_catalog_evidence
from commercepilot.services.competitor_analysis import analyze_competitor_evidence
from commercepilot.services.competitor_intelligence import load_competitor_evidence
from commercepilot.services.review_analysis import analyze_review_evidence
from commercepilot.services.review_intelligence import load_review_evidence
from commercepilot.services.strategy_synthesis import synthesize_strategy

CaseExecutor = Callable[[EvaluationCase], list[EvaluationCheck]]
ProgressCallback = Callable[[EvaluationCase, int, int], None]
EVALUATION_REQUEST_TIMEOUT_SECONDS = 120.0


def _check(name: str, passed: bool, detail: str) -> EvaluationCheck:
    return EvaluationCheck(name=name, passed=passed, detail=detail)


def _review_citation_ids(insight: ReviewInsight) -> set[UUID]:
    citation_ids: set[UUID] = set()
    for theme in [*insight.strengths, *insight.complaints]:
        citation_ids.update(theme.evidence_review_ids)
    for improvement in insight.requested_improvements:
        citation_ids.update(improvement.evidence_review_ids)
    return citation_ids


def score_review_output(
    case: EvaluationCase,
    evidence: ReviewEvidenceSet,
    insight: ReviewInsight,
) -> list[EvaluationCheck]:
    valid_ids = {review.id for review in evidence.reviews}
    cited_ids = _review_citation_ids(insight)
    output_text = insight.model_dump_json().lower()
    checks = [
        _check(
            "product_identity",
            insight.product_sku == evidence.product_sku == case.product_sku,
            f"expected {case.product_sku}; received {insight.product_sku}",
        ),
        _check(
            "citation_validity",
            bool(cited_ids) and cited_ids <= valid_ids,
            f"{len(cited_ids)} cited review IDs; {len(cited_ids - valid_ids)} unknown",
        ),
    ]
    for index, terms in enumerate(case.required_topic_groups, start=1):
        matched = [term for term in terms if term.lower() in output_text]
        checks.append(
            _check(
                f"required_topic_{index}",
                bool(matched),
                f"expected one of {terms}; matched {matched}",
            )
        )
    return checks


def _competitor_citation_ids(insight: CompetitorInsight) -> set[UUID]:
    citation_ids: set[UUID] = set()
    for finding in insight.findings:
        citation_ids.update(finding.evidence_snapshot_ids)
    for recommendation in insight.recommended_actions:
        citation_ids.update(recommendation.evidence_snapshot_ids)
    return citation_ids


def score_competitor_output(
    case: EvaluationCase,
    evidence: CompetitorEvidenceSet,
    insight: CompetitorInsight,
) -> list[EvaluationCheck]:
    valid_ids: set[UUID] = set()
    decreased_competitors: set[str] = set()
    for change in evidence.price_changes:
        valid_ids.add(change.current_snapshot_id)
        if change.previous_snapshot_id is not None:
            valid_ids.add(change.previous_snapshot_id)
        if change.current_price < (change.previous_price or change.current_price):
            decreased_competitors.add(change.competitor_name)

    cited_ids = _competitor_citation_ids(insight)
    finding_names = {finding.competitor_name for finding in insight.findings}
    expected_names = set(case.expected_competitors)
    expected_drops = set(case.expected_price_drop_competitors)
    return [
        _check(
            "product_identity",
            insight.product_sku == evidence.product_sku == case.product_sku,
            f"expected {case.product_sku}; received {insight.product_sku}",
        ),
        _check(
            "citation_validity",
            bool(cited_ids) and cited_ids <= valid_ids,
            f"{len(cited_ids)} cited snapshot IDs; "
            f"{len(cited_ids - valid_ids)} unknown",
        ),
        _check(
            "competitor_coverage",
            expected_names <= finding_names,
            f"expected {sorted(expected_names)}; found {sorted(finding_names)}",
        ),
        _check(
            "price_drop_evidence",
            expected_drops <= decreased_competitors,
            f"expected {sorted(expected_drops)}; evidence shows "
            f"{sorted(decreased_competitors)}",
        ),
    ]


def _topic_checks(
    case: EvaluationCase,
    output_text: str,
) -> list[EvaluationCheck]:
    checks: list[EvaluationCheck] = []
    lowered_text = output_text.lower()
    for index, terms in enumerate(case.required_topic_groups, start=1):
        matched = [term for term in terms if term.lower() in lowered_text]
        checks.append(
            _check(
                f"required_topic_{index}",
                bool(matched),
                f"expected one of {terms}; matched {matched}",
            )
        )
    return checks


def score_strategy_output(
    case: EvaluationCase,
    review_insight: ReviewInsight,
    competitor_insight: CompetitorInsight,
    strategy: CommerceStrategy,
) -> list[EvaluationCheck]:
    valid_ids = _review_citation_ids(review_insight) | _competitor_citation_ids(
        competitor_insight
    )
    cited_ids = {
        evidence_id
        for action in strategy.action_proposals
        for evidence_id in action.evidence_ids
    }
    action_types = {action.action_type for action in strategy.action_proposals}
    forbidden = action_types & set(case.forbidden_action_types)
    state = cast(
        CommercePilotState,
        {
            "strategy": strategy,
            "error": None,
            "force_catalog_update": case.force_catalog_update,
            "force_campaign_update": case.force_campaign_update,
        },
    )
    route = route_after_synthesis(state)
    policy = apply_approval_policy(strategy.action_proposals)
    checks = [
        _check(
            "product_identity",
            strategy.product_sku == case.product_sku,
            f"expected {case.product_sku}; received {strategy.product_sku}",
        ),
        _check(
            "action_count",
            len(strategy.action_proposals) >= case.minimum_action_count,
            f"expected at least {case.minimum_action_count}; "
            f"received {len(strategy.action_proposals)}",
        ),
        _check(
            "citation_validity",
            bool(cited_ids) and cited_ids <= valid_ids,
            f"{len(cited_ids)} cited evidence IDs; "
            f"{len(cited_ids - valid_ids)} unknown",
        ),
        _check(
            "forbidden_actions",
            not forbidden,
            f"forbidden actions returned: {sorted(value.value for value in forbidden)}",
        ),
        _check(
            "agent_routing",
            not case.allowed_routes or route in case.allowed_routes,
            f"route {route}; allowed {case.allowed_routes}",
        ),
        _check(
            "approval_policy_coverage",
            len(policy.actions) == len(strategy.action_proposals),
            f"governed {len(policy.actions)} of "
            f"{len(strategy.action_proposals)} actions",
        ),
    ]
    return checks + _topic_checks(case, strategy.model_dump_json())


def score_catalog_output(
    case: EvaluationCase,
    evidence: CatalogEvidenceSet,
    draft: CatalogDraft,
) -> list[EvaluationCheck]:
    valid_ids = {
        evidence.product.id,
        *_review_citation_ids(evidence.review_insight),
        *_competitor_citation_ids(evidence.competitor_insight),
    }
    supporting_ids = set(draft.supporting_evidence_ids)
    bullet_ids = {
        evidence_id
        for bullet in draft.feature_bullets
        for evidence_id in bullet.evidence_ids
    }
    checks = [
        _check(
            "product_identity",
            draft.product_sku == evidence.product.sku == case.product_sku,
            f"expected {case.product_sku}; received {draft.product_sku}",
        ),
        _check(
            "citation_validity",
            bool(supporting_ids) and supporting_ids <= valid_ids,
            f"{len(supporting_ids)} supporting IDs; "
            f"{len(supporting_ids - valid_ids)} unknown",
        ),
        _check(
            "bullet_grounding",
            bool(bullet_ids) and bullet_ids <= supporting_ids,
            f"{len(bullet_ids)} bullet IDs; "
            f"{len(bullet_ids - supporting_ids)} absent from supporting evidence",
        ),
        _check(
            "catalog_completeness",
            3 <= len(draft.feature_bullets) <= 6
            and 3 <= len(draft.seo_keywords) <= 10,
            f"{len(draft.feature_bullets)} bullets and "
            f"{len(draft.seo_keywords)} keywords",
        ),
    ]
    return checks + _topic_checks(case, draft.model_dump_json())


def score_campaign_output(
    case: EvaluationCase,
    evidence: CampaignEvidenceSet,
    draft: CampaignDraft,
) -> list[EvaluationCheck]:
    valid_ids = {
        evidence.product.id,
        *_review_citation_ids(evidence.review_insight),
        *_competitor_citation_ids(evidence.competitor_insight),
    }
    supporting_ids = set(draft.supporting_evidence_ids)
    asset_ids = {
        evidence_id
        for asset in draft.assets
        for evidence_id in asset.evidence_ids
    }
    channels = {asset.channel for asset in draft.assets}
    expected_channels = set(case.expected_channels)
    checks = [
        _check(
            "product_identity",
            draft.product_sku == evidence.product.sku == case.product_sku,
            f"expected {case.product_sku}; received {draft.product_sku}",
        ),
        _check(
            "citation_validity",
            bool(supporting_ids) and supporting_ids <= valid_ids,
            f"{len(supporting_ids)} supporting IDs; "
            f"{len(supporting_ids - valid_ids)} unknown",
        ),
        _check(
            "asset_grounding",
            bool(asset_ids) and asset_ids <= supporting_ids,
            f"{len(asset_ids)} asset IDs; "
            f"{len(asset_ids - supporting_ids)} absent from supporting evidence",
        ),
        _check(
            "channel_coverage",
            not expected_channels or channels == expected_channels,
            f"expected {sorted(value.value for value in expected_channels)}; "
            f"received {sorted(value.value for value in channels)}",
        ),
    ]
    return checks + _topic_checks(case, draft.model_dump_json())


def _proposal(action_type: ActionType, product_sku: str) -> ActionProposal:
    price_change = None
    if action_type is ActionType.CHANGE_PRICE:
        price_change = PriceChangeParameters(
            sku=product_sku,
            expected_current_price=Decimal("100.00"),
            new_price=Decimal("90.00"),
        )
    return ActionProposal(
        action_type=action_type,
        title=f"Evaluate {action_type.value}",
        description=f"Evaluate governance behavior for {action_type.value} safely.",
        rationale="This controlled proposal verifies routing and approval policy.",
        priority=ImprovementPriority.MEDIUM,
        source_agents=[SourceAgent.ORCHESTRATOR],
        evidence_ids=[uuid4()],
        price_change=price_change,
    )


def score_governance_contract(case: EvaluationCase) -> list[EvaluationCheck]:
    product_sku = case.product_sku or "EVAL-PRODUCT"
    proposals = [
        _proposal(action_type, product_sku)
        for action_type in case.proposed_action_types
    ]
    strategy = CommerceStrategy(
        product_sku=product_sku,
        situation_summary=(
            "Controlled strategy used to evaluate deterministic governance."
        ),
        strategic_objectives=["Validate routing and approval behavior."],
        action_proposals=proposals,
        confidence=1.0,
    )
    state = cast(
        CommercePilotState,
        {
            "strategy": strategy,
            "error": None,
            "force_catalog_update": case.force_catalog_update,
            "force_campaign_update": case.force_campaign_update,
        },
    )
    actual_route = route_after_synthesis(state)
    policy = apply_approval_policy(proposals)
    return [
        _check(
            "agent_routing",
            actual_route == case.expected_route,
            f"expected {case.expected_route}; received {actual_route}",
        ),
        _check(
            "approval_policy",
            policy.requires_human_approval == case.expected_human_approval,
            "expected approval="
            f"{case.expected_human_approval}; received "
            f"{policy.requires_human_approval}",
        ),
    ]


class EvaluationExecutionContext:
    def __init__(self) -> None:
        self._openai_client: OpenAI | None = None
        self.error_cache: dict[tuple[str, str], str] = {}
        self.review_cache: dict[str, tuple[ReviewEvidenceSet, ReviewInsight]] = {}
        self.competitor_cache: dict[
            str, tuple[CompetitorEvidenceSet, CompetitorInsight]
        ] = {}
        self.strategy_cache: dict[str, CommerceStrategy] = {}
        self.catalog_cache: dict[str, tuple[CatalogEvidenceSet, CatalogDraft]] = {}
        self.campaign_cache: dict[
            str, tuple[CampaignEvidenceSet, CampaignDraft]
        ] = {}

    def client(self) -> OpenAI:
        if self._openai_client is not None:
            return self._openai_client
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("COMMERCEPILOT_OPENAI_API_KEY is not configured.")
        self._openai_client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=EVALUATION_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
        return self._openai_client

    def raise_cached_error(self, stage: str, product_sku: str) -> None:
        error = self.error_cache.get((stage, product_sku))
        if error is not None:
            raise RuntimeError(error)

    def cache_error(
        self,
        stage: str,
        product_sku: str,
        error: Exception,
    ) -> None:
        self.error_cache[(stage, product_sku)] = str(error)

    def review_output(
        self,
        product_sku: str,
    ) -> tuple[ReviewEvidenceSet, ReviewInsight]:
        cached = self.review_cache.get(product_sku)
        if cached is not None:
            return cached
        self.raise_cached_error("review", product_sku)
        try:
            with SessionLocal() as session:
                evidence = load_review_evidence(session, product_sku)
            insight = analyze_review_evidence(
                evidence,
                client=self.client(),
                model=get_settings().openai_model,
            )
        except Exception as error:
            self.cache_error("review", product_sku, error)
            raise
        self.review_cache[product_sku] = (evidence, insight)
        return evidence, insight

    def competitor_output(
        self,
        product_sku: str,
    ) -> tuple[CompetitorEvidenceSet, CompetitorInsight]:
        cached = self.competitor_cache.get(product_sku)
        if cached is not None:
            return cached
        self.raise_cached_error("competitor", product_sku)
        try:
            with SessionLocal() as session:
                evidence = load_competitor_evidence(session, product_sku)
            insight = analyze_competitor_evidence(
                evidence,
                client=self.client(),
                model=get_settings().openai_model,
            )
        except Exception as error:
            self.cache_error("competitor", product_sku, error)
            raise
        self.competitor_cache[product_sku] = (evidence, insight)
        return evidence, insight

    def strategy_output(self, product_sku: str) -> CommerceStrategy:
        cached = self.strategy_cache.get(product_sku)
        if cached is not None:
            return cached
        self.raise_cached_error("strategy", product_sku)
        _, review_insight = self.review_output(product_sku)
        _, competitor_insight = self.competitor_output(product_sku)
        try:
            strategy = synthesize_strategy(
                review_insight,
                competitor_insight,
                client=self.client(),
                model=get_settings().openai_model,
            )
        except Exception as error:
            self.cache_error("strategy", product_sku, error)
            raise
        self.strategy_cache[product_sku] = strategy
        return strategy

    def catalog_output(
        self,
        product_sku: str,
    ) -> tuple[CatalogEvidenceSet, CatalogDraft]:
        cached = self.catalog_cache.get(product_sku)
        if cached is not None:
            return cached
        self.raise_cached_error("catalog", product_sku)
        _, review_insight = self.review_output(product_sku)
        _, competitor_insight = self.competitor_output(product_sku)
        try:
            with SessionLocal() as session:
                evidence = load_catalog_evidence(
                    session,
                    product_sku,
                    review_insight,
                    competitor_insight,
                )
            draft = generate_catalog_draft(
                evidence,
                client=self.client(),
                model=get_settings().openai_model,
            )
        except Exception as error:
            self.cache_error("catalog", product_sku, error)
            raise
        self.catalog_cache[product_sku] = (evidence, draft)
        return evidence, draft

    def campaign_output(
        self,
        product_sku: str,
    ) -> tuple[CampaignEvidenceSet, CampaignDraft]:
        cached = self.campaign_cache.get(product_sku)
        if cached is not None:
            return cached
        self.raise_cached_error("campaign", product_sku)
        _, review_insight = self.review_output(product_sku)
        _, competitor_insight = self.competitor_output(product_sku)
        strategy = self.strategy_output(product_sku)
        _, catalog_draft = self.catalog_output(product_sku)
        with SessionLocal() as session:
            product = session.scalar(
                select(Product).where(Product.sku == product_sku)
            )
            if product is None:
                raise RuntimeError(f"Product not found: {product_sku}")
            product_read = ProductRead.model_validate(product).model_copy(
                update={
                    "seo_title": catalog_draft.seo_title,
                    "meta_description": catalog_draft.meta_description,
                    "description": catalog_draft.product_description,
                    "feature_bullets": [
                        bullet.model_dump(mode="json")
                        for bullet in catalog_draft.feature_bullets
                    ],
                    "seo_keywords": catalog_draft.seo_keywords,
                    "target_audience": catalog_draft.target_audience,
                }
            )
        evidence = CampaignEvidenceSet(
            product=product_read,
            review_insight=review_insight,
            competitor_insight=competitor_insight,
            strategy=strategy,
        )
        try:
            draft = generate_campaign_draft(
                evidence,
                client=self.client(),
                model=get_settings().openai_model,
            )
        except Exception as error:
            self.cache_error("campaign", product_sku, error)
            raise
        self.campaign_cache[product_sku] = (evidence, draft)
        return evidence, draft

    def execute_review(self, case: EvaluationCase) -> list[EvaluationCheck]:
        evidence, insight = self.review_output(cast(str, case.product_sku))
        return score_review_output(case, evidence, insight)

    def execute_competitor(self, case: EvaluationCase) -> list[EvaluationCheck]:
        evidence, insight = self.competitor_output(cast(str, case.product_sku))
        return score_competitor_output(case, evidence, insight)

    def execute_strategy(self, case: EvaluationCase) -> list[EvaluationCheck]:
        product_sku = cast(str, case.product_sku)
        _, review_insight = self.review_output(product_sku)
        _, competitor_insight = self.competitor_output(product_sku)
        strategy = self.strategy_output(product_sku)
        return score_strategy_output(
            case,
            review_insight,
            competitor_insight,
            strategy,
        )

    def execute_catalog(self, case: EvaluationCase) -> list[EvaluationCheck]:
        evidence, draft = self.catalog_output(cast(str, case.product_sku))
        return score_catalog_output(case, evidence, draft)

    def execute_campaign(self, case: EvaluationCase) -> list[EvaluationCheck]:
        evidence, draft = self.campaign_output(cast(str, case.product_sku))
        return score_campaign_output(case, evidence, draft)

    def executors(self) -> dict[EvaluationTarget, CaseExecutor]:
        return {
            EvaluationTarget.REVIEW_AGENT: self.execute_review,
            EvaluationTarget.COMPETITOR_AGENT: self.execute_competitor,
            EvaluationTarget.STRATEGY: self.execute_strategy,
            EvaluationTarget.CATALOG_AGENT: self.execute_catalog,
            EvaluationTarget.CAMPAIGN_AGENT: self.execute_campaign,
            EvaluationTarget.GOVERNANCE: score_governance_contract,
        }


def run_evaluation(
    cases: Sequence[EvaluationCase],
    *,
    executors: dict[EvaluationTarget, CaseExecutor] | None = None,
    progress: ProgressCallback | None = None,
) -> EvaluationReport:
    configured_executors = executors or EvaluationExecutionContext().executors()
    results: list[EvaluationCaseResult] = []
    total_cases = len(cases)
    for index, case in enumerate(cases, start=1):
        if progress is not None:
            progress(case, index, total_cases)
        started = perf_counter()
        checks: list[EvaluationCheck] = []
        error: str | None = None
        try:
            checks = configured_executors[case.target](case)
        except Exception as exception:
            error = str(exception)
        latency_ms = round((perf_counter() - started) * 1000, 2)
        passed = error is None and bool(checks) and all(
            check.passed for check in checks
        )
        results.append(
            EvaluationCaseResult(
                case_id=case.id,
                case_name=case.name,
                target=case.target,
                product_sku=case.product_sku,
                passed=passed,
                latency_ms=latency_ms,
                checks=checks,
                error=error,
            )
        )

    passed_cases = sum(result.passed for result in results)
    total_cases = len(results)
    return EvaluationReport(
        generated_at=datetime.now(UTC),
        model=get_settings().openai_model,
        total_cases=total_cases,
        passed_cases=passed_cases,
        pass_rate=passed_cases / total_cases if total_cases else 0,
        average_latency_ms=(
            round(sum(result.latency_ms for result in results) / total_cases, 2)
            if total_cases
            else 0
        ),
        results=results,
    )
