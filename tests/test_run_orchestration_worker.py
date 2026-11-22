from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from scripts.run_orchestration_worker import main, process_pending_runs


@pytest.mark.asyncio
@patch("scripts.run_orchestration_worker.execute_orchestration_run")
@patch("scripts.run_orchestration_worker.SessionLocal")
async def test_process_pending_runs_executes_each_discovered_run(
    session_factory: MagicMock,
    execute_run: AsyncMock,
) -> None:
    run_ids = [uuid4(), uuid4()]
    with patch(
        "scripts.run_orchestration_worker.list_pending_run_ids",
        return_value=run_ids,
    ):
        processed = await process_pending_runs()

    assert processed == 2
    session_factory.assert_called_once()
    assert execute_run.await_count == 2
    execute_run.assert_any_await(run_ids[0])
    execute_run.assert_any_await(run_ids[1])


@pytest.mark.asyncio
@patch(
    "scripts.run_orchestration_worker.process_pending_runs",
    new_callable=AsyncMock,
    return_value=0,
)
async def test_worker_once_exits_after_single_poll(
    process_runs: AsyncMock,
) -> None:
    await main(once=True, poll_interval=2.0)

    process_runs.assert_awaited_once()


@pytest.mark.asyncio
async def test_worker_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        await main(once=True, poll_interval=0)
