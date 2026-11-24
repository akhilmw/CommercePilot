import argparse
from datetime import datetime
from pathlib import Path

from commercepilot.evaluation.models import EvaluationCase
from commercepilot.evaluation.runner import run_evaluation
from commercepilot.evaluation.scenarios import EVALUATION_CASES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run controlled CommercePilot agent evaluations."
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Run one case ID. Repeat to select multiple cases.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path.",
    )
    return parser.parse_args()


def select_cases(case_ids: list[str] | None):
    if not case_ids:
        return EVALUATION_CASES
    selected = tuple(case for case in EVALUATION_CASES if case.id in case_ids)
    missing = set(case_ids) - {case.id for case in selected}
    if missing:
        raise ValueError(f"Unknown evaluation case IDs: {', '.join(sorted(missing))}")
    return selected


def main() -> None:
    arguments = parse_args()
    cases = select_cases(arguments.case_ids)
    def show_progress(case: EvaluationCase, index: int, total: int) -> None:
        print(
            f"[{index:02d}/{total:02d}] {case.id} ({case.target.value})",
            flush=True,
        )

    report = run_evaluation(cases, progress=show_progress)
    output = arguments.output or Path(
        "artifacts/evaluations/"
        f"agent-evaluation-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n")

    print(f"{'Case':<42} {'Target':<18} {'Result':<8} {'Latency ms':>10}")
    print("-" * 82)
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"{result.case_id:<42} {result.target.value:<18} "
            f"{status:<8} {result.latency_ms:>10.1f}"
        )
        if result.error:
            print(f"  error: {result.error}")
        for check in result.checks:
            marker = "✓" if check.passed else "✗"
            print(f"  {marker} {check.name}: {check.detail}")
    print()
    print(
        f"Passed {report.passed_cases}/{report.total_cases} "
        f"({report.pass_rate:.0%}); average latency "
        f"{report.average_latency_ms:.1f} ms"
    )
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
