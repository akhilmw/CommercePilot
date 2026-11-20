package mcpserver

import (
	"net/http"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/akhilmw/commercepilot/mcp-server/internal/tools"
)

func New(
	priceUpdater tools.PriceUpdater,
	catalogPublisher tools.CatalogPublisher,
	campaignLauncher tools.CampaignLauncher,
) *mcp.Server {
	server := mcp.NewServer(
		&mcp.Implementation{
			Name:    "commercepilot-mcp",
			Version: "0.1.0",
		},
		nil,
	)

	priceTool := tools.NewUpdateProductPriceTool(priceUpdater)
	mcp.AddTool(
		server,
		&mcp.Tool{
			Name: "update_product_price",
			Description: "Execute one approved, idempotent product price update. " +
				"Rejects missing approvals, altered payloads, and stale prices.",
		},
		priceTool.Handle,
	)

	catalogTool := tools.NewPublishCatalogUpdateTool(catalogPublisher)
	mcp.AddTool(
		server,
		&mcp.Tool{
			Name: "publish_catalog_update",
			Description: "Publish one exact, human-approved catalog draft. " +
				"Rejects altered approvals, missing drafts, and stale catalog versions.",
		},
		catalogTool.Handle,
	)

	campaignTool := tools.NewLaunchCampaignTool(campaignLauncher)
	mcp.AddTool(
		server,
		&mcp.Tool{
			Name: "launch_campaign",
			Description: "Launch one exact, human-approved campaign draft. " +
				"Rejects altered approvals and stale catalog or price state.",
		},
		campaignTool.Handle,
	)
	return server
}

func HTTPHandler(server *mcp.Server) http.Handler {
	return mcp.NewStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server },
		&mcp.StreamableHTTPOptions{
			JSONResponse: true,
			Stateless:    true,
		},
	)
}
