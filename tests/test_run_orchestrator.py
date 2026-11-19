from scripts.run_orchestrator import format_approval_action


def test_format_price_change_for_human_approval() -> None:
    lines = format_approval_action(
        {
            "action_type": "change_price",
            "title": "Temporary competitor price match",
            "rationale": "A competitor is running a limited-time promotion.",
            "price_change": {
                "sku": "NOVA-AUDIO-001",
                "expected_current_price": "129.99",
                "new_price": "109.99",
                "currency": "USD",
            },
        }
    )

    assert lines == [
        "- change_price: Temporary competitor price match",
        "  SKU: NOVA-AUDIO-001",
        "  Current price: USD 129.99",
        "  Proposed price: USD 109.99",
        "  Change: USD -20.00 (-15.39%)",
        "  Reason: A competitor is running a limited-time promotion.",
    ]
