from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from commercepilot.mcp.client import (
    CommercePilotMCPClient,
    MCPToolExecutionError,
    PublishCatalogUpdateRequest,
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


def make_catalog_request() -> PublishCatalogUpdateRequest:
    return PublishCatalogUpdateRequest(
        action_id="bca633e6-3a85-492b-ac2e-f731b8fac20d",
        idempotency_key="catalog-publish:bca633e6",
        draft_id="bca633e6-3a85-492b-ac2e-f731b8fac20d",
        sku="NOVA-AUDIO-001",
        expected_catalog_version=1,
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


@pytest.mark.asyncio
@patch("commercepilot.mcp.client.Client")
async def test_publish_catalog_update_returns_structured_result(
    client_factory: AsyncMock,
) -> None:
    session = client_factory.return_value.__aenter__.return_value
    session.call_tool.return_value = SimpleNamespace(
        structured_content={
            "status": "executed",
            "action_id": make_catalog_request().action_id,
            "draft_id": make_catalog_request().draft_id,
            "sku": "NOVA-AUDIO-001",
            "previous_catalog_version": 1,
            "current_catalog_version": 2,
            "published_at": "2026-11-19T23:00:00Z",
            "replayed": False,
        },
        is_error=False,
    )

    result = await CommercePilotMCPClient(
        "http://localhost:8081"
    ).publish_catalog_update(make_catalog_request())

    assert result.status == "executed"
    assert result.current_catalog_version == 2
    session.call_tool.assert_awaited_once_with(
        "publish_catalog_update",
        arguments=make_catalog_request().model_dump(mode="json"),
    )


@pytest.mark.asyncio
@patch("commercepilot.mcp.client.Client")
async def test_publish_catalog_update_raises_structured_tool_error(
    client_factory: AsyncMock,
) -> None:
    session = client_factory.return_value.__aenter__.return_value
    session.call_tool.return_value = SimpleNamespace(
        structured_content={
            "status": "rejected",
            "action_id": make_catalog_request().action_id,
            "draft_id": make_catalog_request().draft_id,
            "sku": "NOVA-AUDIO-001",
            "replayed": False,
            "error_code": "stale_catalog",
            "message": "product catalog changed after approval",
        },
        is_error=True,
    )

    with pytest.raises(MCPToolExecutionError, match="stale_catalog"):
        await CommercePilotMCPClient(
            "http://localhost:8081"
        ).publish_catalog_update(make_catalog_request())
