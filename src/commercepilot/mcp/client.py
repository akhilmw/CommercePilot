from mcp import Client
from pydantic import BaseModel


class UpdateProductPriceRequest(BaseModel):
    action_id: str
    idempotency_key: str
    sku: str
    expected_current_price: str
    new_price: str


class UpdateProductPriceResult(BaseModel):
    status: str
    action_id: str
    sku: str
    previous_price: str | None = None
    current_price: str | None = None
    executed_at: str | None = None
    replayed: bool
    error_code: str | None = None
    message: str | None = None


class PublishCatalogUpdateRequest(BaseModel):
    action_id: str
    idempotency_key: str
    draft_id: str
    sku: str
    expected_catalog_version: int


class PublishCatalogUpdateResult(BaseModel):
    status: str
    action_id: str
    draft_id: str
    sku: str
    previous_catalog_version: int | None = None
    current_catalog_version: int | None = None
    published_at: str | None = None
    replayed: bool
    error_code: str | None = None
    message: str | None = None


class LaunchCampaignRequest(BaseModel):
    action_id: str
    idempotency_key: str
    draft_id: str
    sku: str
    source_catalog_version: int
    source_price: str


class LaunchCampaignResult(BaseModel):
    status: str
    action_id: str
    draft_id: str
    sku: str
    launched_at: str | None = None
    replayed: bool
    error_code: str | None = None
    message: str | None = None


class MCPToolExecutionError(RuntimeError):
    def __init__(
        self,
        result: (
            UpdateProductPriceResult | PublishCatalogUpdateResult | LaunchCampaignResult
        ),
    ) -> None:
        self.result = result
        super().__init__(f"{result.error_code}: {result.message}")


class CommercePilotMCPClient:
    def __init__(self, base_url: str) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/mcp"

    async def update_product_price(
        self,
        request: UpdateProductPriceRequest,
    ) -> UpdateProductPriceResult:
        async with Client(self.endpoint) as client:
            response = await client.call_tool(
                "update_product_price",
                arguments=request.model_dump(mode="json"),
            )

        if response.structured_content is None:
            raise RuntimeError("MCP tool returned no structured content.")

        result = UpdateProductPriceResult.model_validate(response.structured_content)
        if response.is_error:
            raise MCPToolExecutionError(result)
        return result

    async def publish_catalog_update(
        self,
        request: PublishCatalogUpdateRequest,
    ) -> PublishCatalogUpdateResult:
        async with Client(self.endpoint) as client:
            response = await client.call_tool(
                "publish_catalog_update",
                arguments=request.model_dump(mode="json"),
            )

        if response.structured_content is None:
            raise RuntimeError("MCP tool returned no structured content.")

        result = PublishCatalogUpdateResult.model_validate(response.structured_content)
        if response.is_error:
            raise MCPToolExecutionError(result)
        return result

    async def launch_campaign(
        self,
        request: LaunchCampaignRequest,
    ) -> LaunchCampaignResult:
        async with Client(self.endpoint) as client:
            response = await client.call_tool(
                "launch_campaign",
                arguments=request.model_dump(mode="json"),
            )

        if response.structured_content is None:
            raise RuntimeError("MCP tool returned no structured content.")

        result = LaunchCampaignResult.model_validate(response.structured_content)
        if response.is_error:
            raise MCPToolExecutionError(result)
        return result
