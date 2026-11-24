import pytest

from commercepilot.evaluation.models import (
    EvaluationCase,
    EvaluationCheck,
    EvaluationTarget,
)
from commercepilot.evaluation.runner import (
    run_evaluation,
    score_governance_contract,
)
from commercepilot.evaluation.scenarios import (
    EVALUATION_CASES,
    INITIAL_EVALUATION_CASES,
)


def test_initial_suite_contains_five_unique_cases() -> None:
    assert len(INITIAL_EVALUATION_CASES) == 5
    assert len({case.id for case in INITIAL_EVALUATION_CASES}) == 5
    assert {case.target for case in INITIAL_EVALUATION_CASES} == {
        EvaluationTarget.REVIEW_AGENT,
        EvaluationTarget.COMPETITOR_AGENT,
        EvaluationTarget.GOVERNANCE,
    }


def test_full_suite_contains_thirty_cases_across_every_layer() -> None:
    assert len(EVALUATION_CASES) == 30
    assert len({case.id for case in EVALUATION_CASES}) == 30
    counts = {
        target: sum(case.target is target for case in EVALUATION_CASES)
        for target in EvaluationTarget
    }
    assert counts == {
        EvaluationTarget.REVIEW_AGENT: 6,
        EvaluationTarget.COMPETITOR_AGENT: 6,
        EvaluationTarget.STRATEGY: 6,
        EvaluationTarget.CATALOG_AGENT: 6,
        EvaluationTarget.CAMPAIGN_AGENT: 2,
        EvaluationTarget.GOVERNANCE: 4,
    }


def test_agent_case_requires_product_sku() -> None:
    with pytest.raises(ValueError, match="require a product SKU"):
        EvaluationCase(
            id="missing-product",
            name="Missing product evaluation case",
            target=EvaluationTarget.REVIEW_AGENT,
        )


def test_governance_case_passes_routing_and_approval_contract() -> None:
    case = next(
        case
        for case in INITIAL_EVALUATION_CASES
        if case.target is EvaluationTarget.GOVERNANCE
    )

    checks = score_governance_contract(case)

    assert {check.name for check in checks} == {
        "agent_routing",
        "approval_policy",
    }
    assert all(check.passed for check in checks)


def test_run_evaluation_aggregates_injected_case_results() -> None:
    cases = INITIAL_EVALUATION_CASES[:2]

    def passing_executor(_case: EvaluationCase) -> list[EvaluationCheck]:
        return [EvaluationCheck(name="contract", passed=True, detail="passed")]

    report = run_evaluation(
        cases,
        executors={EvaluationTarget.REVIEW_AGENT: passing_executor},
    )

    assert report.total_cases == 2
    assert report.passed_cases == 2
    assert report.pass_rate == 1.0
    assert all(result.passed for result in report.results)


def test_run_evaluation_records_executor_failures() -> None:
    case = INITIAL_EVALUATION_CASES[0]

    def failing_executor(_case: EvaluationCase) -> list[EvaluationCheck]:
        raise RuntimeError("synthetic evaluation failure")

    report = run_evaluation(
        [case],
        executors={EvaluationTarget.REVIEW_AGENT: failing_executor},
    )

    assert report.passed_cases == 0
    assert report.results[0].passed is False
    assert report.results[0].error == "synthetic evaluation failure"


def test_full_suite_dispatches_through_injected_executors() -> None:
    def passing_executor(_case: EvaluationCase) -> list[EvaluationCheck]:
        return [EvaluationCheck(name="contract", passed=True, detail="passed")]

    report = run_evaluation(
        EVALUATION_CASES,
        executors={target: passing_executor for target in EvaluationTarget},
    )

    assert report.total_cases == 30
    assert report.passed_cases == 30
