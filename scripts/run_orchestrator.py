from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from commercepilot.graph.orchestrator_graph import build_orchestrator_graph
from commercepilot.graph.orchestrator_state import CommercePilotState


def main() -> None:
    graph = build_orchestrator_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = graph.invoke(
        CommercePilotState(
            product_sku="NOVA-AUDIO-001",
            review_insight=None,
            competitor_insight=None,
            strategy=None,
            approval_policy=None,
            approval_decision=None,
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
            print(f"- {action['action_type']}: {action['title']}")

        answer = input("\nApprove these actions? [y/N]: ").strip().lower()
        comment = input("Optional comment: ").strip() or None
        result = graph.invoke(
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


if __name__ == "__main__":
    main()
