import argparse
import asyncio

from commercepilot.db.session import SessionLocal
from commercepilot.services.orchestration_execution import (
    execute_orchestration_run,
    list_pending_run_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute pending CommercePilot orchestration runs."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process currently pending runs and exit.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between database polls when running continuously.",
    )
    return parser.parse_args()


async def process_pending_runs() -> int:
    with SessionLocal() as session:
        run_ids = list_pending_run_ids(session)
    for run_id in run_ids:
        await execute_orchestration_run(run_id)
    return len(run_ids)


async def main(*, once: bool, poll_interval: float) -> None:
    if poll_interval <= 0:
        raise ValueError("poll interval must be greater than zero")

    while True:
        processed = await process_pending_runs()
        if once:
            print(f"Processed {processed} pending run(s).")
            return
        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(
        main(
            once=arguments.once,
            poll_interval=arguments.poll_interval,
        )
    )
