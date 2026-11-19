from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from commercepilot.mcp.client import (
    CommercePilotMCPClient,
    MCPToolExecutionError,
    UpdateProductPriceRequest,
)


def make_request() -> UpdateProductPriceRequest:
    return UpdateProductPriceRequest(
        action_id="af2bc39c-6b34-45f8-9f7a-d9e2932e03dc",
        idempotency_key="price-change:test",
        sku="NOVA-AUDIO-001",
        expected_current_price="129.99",
        new_price="119.99",
    )


@pytest.mark.asyncio
@patch("commercepilot.mcp.client.Client")
async def test_update_product_price_returns_structured_result(
    client_factory: AsyncMock,
) -> None:
    session = client_factory.return_value.__aenter__.return_value
    session.call_tool.return_value = SimpleNamespace(
        structured_content={
            "status": "executed",
            "action_id": make_request().action_id,
            "sku": "NOVA-AUDIO-001",
            "previous_price": "129.99",
            "current_price": "119.99",
            "executed_at": "2026-11-19T12:00:00Z",
            "replayed": False,
        },
        is_error=False,
    )

    result = await CommercePilotMCPClient(
        "http://localhost:8081"
    ).update_product_price(make_request())

    assert result.status == "executed"
    assert result.current_price == "119.99"
    session.call_tool.assert_awaited_once_with(
        "update_product_price",
        arguments=make_request().model_dump(mode="json"),
    )


@pytest.mark.asyncio
@patch("commercepilot.mcp.client.Client")
async def test_update_product_price_raises_structured_tool_error(
    client_factory: AsyncMock,
) -> None:
    session = client_factory.return_value.__aenter__.return_value
    session.call_tool.return_value = SimpleNamespace(
        structured_content={
            "status": "rejected",
            "action_id": make_request().action_id,
            "sku": "NOVA-AUDIO-001",
            "replayed": False,
            "error_code": "approval_not_found",
            "message": "approved action not found",
        },
        is_error=True,
    )

    with pytest.raises(MCPToolExecutionError, match="approval_not_found"):
        await CommercePilotMCPClient(
            "http://localhost:8081"
        ).update_product_price(make_request())
