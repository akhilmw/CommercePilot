import argparse
import asyncio
import json
from decimal import Decimal
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from commercepilot.graph.checkpoint import build_orchestrator_checkpointer
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
        difference / current_price * Decimal("100") if current_price else Decimal("0")
    )

    lines.extend(
        [
            f"  SKU: {price_change['sku']}",
            f"  Current price: {currency} {current_price:.2f}",
            f"  Proposed price: {currency} {new_price:.2f}",
            (f"  Change: {currency} {difference:+.2f} ({percent_change:+.2f}%)"),
            f"  Reason: {action['rationale']}",
        ]
    )
    return lines


def format_catalog_comparison(comparison: dict[str, Any]) -> list[str]:
    lines = [
        (
            "Catalog version: "
            f"{comparison['current_catalog_version']} "
            f"(draft expects {comparison['expected_catalog_version']})"
        )
    ]
    for field in comparison["fields"]:
        if not field["changed"]:
            continue
        current = json.dumps(
            field["current_value"],
            indent=2,
            ensure_ascii=False,
        )
        proposed = json.dumps(
            field["proposed_value"],
            indent=2,
            ensure_ascii=False,
        )
        lines.extend(
            [
                f"\n{field['label']}:",
                f"- {current}",
                f"+ {proposed}",
            ]
        )
    return lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the CommercePilot orchestration workflow."
    )
    parser.add_argument(
        "--force-catalog",
        action="store_true",
        help=(
            "Run the catalog draft, verification, approval, and MCP publish "
            "path even when strategy synthesis does not propose it."
        ),
    )
    return parser.parse_args()


async def main(*, force_catalog: bool = False) -> None:
    graph = build_orchestrator_graph(checkpointer=build_orchestrator_checkpointer())
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = await graph.ainvoke(
        CommercePilotState(
            product_sku="NOVA-AUDIO-001",
            force_catalog_update=force_catalog,
            review_insight=None,
            competitor_insight=None,
            strategy=None,
            catalog_draft=None,
            catalog_draft_id=None,
            catalog_comparison=None,
            catalog_approval_decision=None,
            catalog_publish_action_id=None,
            catalog_execution_result=None,
            approval_policy=None,
            approval_decision=None,
            approved_action_ids=[],
            execution_results=[],
            review_error=None,
            competitor_error=None,
            catalog_error=None,
            error=None,
        ),
        config=config,
    )

    interrupts = result.get("__interrupt__", ())
    while interrupts:
        payload = interrupts[0].value
        print("\nCommercePilot paused for human approval.")
        print(f"Product: {payload['product_sku']}")

        if payload["type"] == "catalog_publish_approval_required":
            print(f"Catalog draft: {payload['draft_id']}")
            print("\nProposed catalog changes:")
            for line in format_catalog_comparison(payload["comparison"]):
                print(line)
            prompt = "\nApprove this catalog draft for publishing? [y/N]: "
        elif payload["type"] == "human_approval_required":
            print("\nPending actions:")
            for action in payload["actions"]:
                for line in format_approval_action(action):
                    print(line)
            prompt = "\nApprove these actions? [y/N]: "
        else:
            raise RuntimeError(f"Unknown approval request type: {payload['type']}")

        answer = input(prompt).strip().lower()
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
        interrupts = result.get("__interrupt__", ())

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

    catalog_draft = result["catalog_draft"]
    if catalog_draft is not None:
        print("\nCatalog Agent draft:")
        print(catalog_draft.model_dump_json(indent=2))
        print(f"\nSaved catalog draft ID: {result['catalog_draft_id']}")
        catalog_decision = result["catalog_approval_decision"]
        if catalog_decision is not None:
            print(f"Catalog publish approved: {catalog_decision.approved}")
            print(f"Catalog publish action ID: {result['catalog_publish_action_id']}")
            catalog_execution = result["catalog_execution_result"]
            if catalog_execution is not None:
                print(
                    "Catalog publication: version "
                    f"{catalog_execution.previous_catalog_version} -> "
                    f"{catalog_execution.current_catalog_version} "
                    f"({catalog_execution.status})"
                )

    print(f"\nAdditional strategy approval required: {policy.requires_human_approval}")
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
    arguments = parse_args()
    asyncio.run(main(force_catalog=arguments.force_catalog))
