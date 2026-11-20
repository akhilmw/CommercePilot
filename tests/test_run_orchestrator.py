from scripts.run_orchestrator import (
    format_approval_action,
    format_campaign_preview,
    format_catalog_comparison,
    parse_args,
)


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


def test_format_catalog_comparison_shows_only_changed_fields() -> None:
    lines = format_catalog_comparison(
        {
            "current_catalog_version": 1,
            "expected_catalog_version": 1,
            "fields": [
                {
                    "label": "SEO title",
                    "current_value": "NovaSound Pro",
                    "proposed_value": "NovaSound Pro Wireless ANC Headphones",
                    "changed": True,
                },
                {
                    "label": "Product description",
                    "current_value": "Unchanged description",
                    "proposed_value": "Unchanged description",
                    "changed": False,
                },
            ],
        }
    )

    assert lines == [
        "Catalog version: 1 (draft expects 1)",
        "\nSEO title:",
        '- "NovaSound Pro"',
        '+ "NovaSound Pro Wireless ANC Headphones"',
    ]


def test_parse_args_enables_forced_catalog_path(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["run_orchestrator.py", "--force-catalog"],
    )

    assert parse_args().force_catalog is True


def test_format_campaign_preview_shows_launch_payload() -> None:
    lines = format_campaign_preview(
        {
            "name": "NovaSound Launch",
            "objective": "Increase qualified product visits.",
            "target_audience": "Commuters and travelers.",
            "core_message": "Focused listening for long journeys.",
            "duration_days": 21,
            "source_catalog_version": 3,
            "source_price": "99.99",
            "assets": [
                {
                    "channel": "social",
                    "headline": "Hear the journey",
                    "body": "Balanced sound and long battery life.",
                    "call_to_action": "Explore NovaSound Pro",
                }
            ],
            "success_metrics": ["click-through rate", "conversion rate"],
        }
    )

    assert "Campaign: NovaSound Launch" in lines
    assert "Evidence snapshot: catalog version 3, price 99.99" in lines
    assert "\n[SOCIAL]" in lines
    assert "\nSuccess metrics: click-through rate, conversion rate" in lines


def test_parse_args_enables_forced_campaign_path(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["run_orchestrator.py", "--force-campaign"],
    )

    arguments = parse_args()
    assert arguments.force_campaign is True
    assert arguments.force_catalog is False
