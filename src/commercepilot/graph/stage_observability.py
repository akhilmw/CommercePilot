from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

from commercepilot.core.model_usage import collect_model_usage, usage_details
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.models.orchestration_api import RunTimelineEvent

StageObserver = Callable[[RunTimelineEvent], None]


class StageNode(Protocol):
    def __call__(self, state: CommercePilotState) -> dict[str, Any]: ...


def observe_stage(
    node: StageNode,
    title: str,
    observer: StageObserver | None,
) -> StageNode:
    if observer is None:
        return node

    def observed(state: CommercePilotState) -> dict[str, Any]:
        start = perf_counter()
        failed = True
        with collect_model_usage() as usage:
            try:
                result = node(state)
                failed = any(
                    value is not None
                    for key, value in result.items()
                    if key == "error" or key.endswith("_error")
                )
                return result
            finally:
                observer(
                    RunTimelineEvent(
                        id=f"stage:{uuid4()}",
                        event_type="agent_stage",
                        title=title,
                        status="failed" if failed else "completed",
                        occurred_at=datetime.now(UTC),
                        details={
                            "duration_ms": round((perf_counter() - start) * 1000),
                            **usage_details(usage),
                        },
                    )
                )

    return observed
