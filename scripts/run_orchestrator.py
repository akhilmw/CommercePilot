import asyncio
from decimal import Decimal
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from commercepilot.graph.orchestrator_graph import build_orchestrator_graph
from commercepilot.graph.orchestrator_state import CommercePilotState


def format_approval_action(action: dict[str, Any]) -> list[str]:
    lines = [f"- {action['action_type']}: {action['title']}"]
    price_change = action.get("price_change")
    if action["action_type"] != "change_price" or price_change is None:
        lines.append(f"  Reason: {action['rationale']}")
        return lines

    current_price = Decimal(price_change["expected_current_price"])
    new_price = Decimal(price_change["new_price"])
    currency = price_change["currency"]
    difference = new_price - current_price
    percent_change = (
        difference / current_price * Decimal("100")
        if current_price
        else Decimal("0")
    )

    lines.extend(
        [
            f"  SKU: {price_change['sku']}",
            f"  Current price: {currency} {current_price:.2f}",
            f"  Proposed price: {currency} {new_price:.2f}",
            (
                f"  Change: {currency} {difference:+.2f} "
                f"({percent_change:+.2f}%)"
            ),
            f"  Reason: {action['rationale']}",
        ]
    )
    return lines


async def main() -> None:
    graph = build_orchestrator_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = await graph.ainvoke(
        CommercePilotState(
            product_sku="NOVA-AUDIO-001",
            review_insight=None,
            competitor_insight=None,
            strategy=None,
            approval_policy=None,
            approval_decision=None,
            approved_action_ids=[],
            execution_results=[],
            review_error=None,
            competitor_error=None,
            error=None,
        ),
        config=config,
    )

    interrupts = result.get("__interrupt__", ())
    if interrupts:
        payload = interrupts[0].value
        print("\nCommercePilot paused for human approval.")
        print(f"Product: {payload['product_sku']}")
        print("\nPending actions:")
        for action in payload["actions"]:
            for line in format_approval_action(action):
                print(line)

        answer = input("\nApprove these actions? [y/N]: ").strip().lower()
        comment = input("Optional comment: ").strip() or None
        result = await graph.ainvoke(
            Command(
                resume={
                    "approved": answer in {"y", "yes"},
                    "reviewer": "local-user",
                    "comment": comment,
                }
            ),
            config=config,
        )

    if result["error"] is not None:
        raise RuntimeError(result["error"])

    strategy = result["strategy"]
    policy = result["approval_policy"]
    if strategy is None or policy is None:
        raise RuntimeError("The orchestrator returned an incomplete result.")

    print("CommercePilot orchestration completed.")
    print(f"Product: {strategy.product_sku}")
    print(f"Confidence: {strategy.confidence}")
    print(f"\nSituation:\n{strategy.situation_summary}")
    print("\nGoverned actions:")
    for action in policy.actions:
        approval = "APPROVAL REQUIRED" if action.requires_human_approval else "SAFE"
        print(f"- [{approval}] {action.action_type}: {action.title}")

    print(
        "\nHuman approval required: "
        f"{policy.requires_human_approval}"
    )
    decision = result["approval_decision"]
    if decision is not None:
        print(f"Human approved: {decision.approved}")
        if decision.comment is not None:
            print(f"Comment: {decision.comment}")
    if result["execution_results"]:
        print("\nMCP execution results:")
        for execution in result["execution_results"]:
            print(
                f"- {execution.sku}: {execution.previous_price} -> "
                f"{execution.current_price} ({execution.status})"
            )


if __name__ == "__main__":
    asyncio.run(main())
