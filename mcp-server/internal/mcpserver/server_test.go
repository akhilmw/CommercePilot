package mcpserver

import (
	"context"
	"net/http/httptest"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/akhilmw/commercepilot/mcp-server/internal/tools"
)

type fakePriceUpdater struct{}

func (fakePriceUpdater) ExecutePriceUpdate(
	_ context.Context,
	_ tools.UpdateProductPriceInput,
) (tools.UpdateProductPriceOutput, error) {
	return tools.UpdateProductPriceOutput{}, nil
}

func TestStreamableHTTPExposesUpdateProductPrice(t *testing.T) {
	t.Parallel()

	server := New(fakePriceUpdater{})
	httpServer := httptest.NewServer(HTTPHandler(server))
	defer httpServer.Close()

	client := mcp.NewClient(
		&mcp.Implementation{Name: "commercepilot-http-test", Version: "0.1.0"},
		nil,
	)
	session, err := client.Connect(
		context.Background(),
		&mcp.StreamableClientTransport{Endpoint: httpServer.URL},
		nil,
	)
	if err != nil {
		t.Fatalf("connect streamable HTTP client: %v", err)
	}
	defer session.Close()

	result, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatalf("list tools over streamable HTTP: %v", err)
	}
	if len(result.Tools) != 1 || result.Tools[0].Name != "update_product_price" {
		t.Fatalf("unexpected tools result: %#v", result.Tools)
	}
}

func TestServerExposesOnlyUpdateProductPrice(t *testing.T) {
	t.Parallel()

	ctx := context.Background()
	server := New(fakePriceUpdater{})
	client := mcp.NewClient(
		&mcp.Implementation{Name: "commercepilot-test", Version: "0.1.0"},
		nil,
	)
	serverTransport, clientTransport := mcp.NewInMemoryTransports()

	serverSession, err := server.Connect(ctx, serverTransport, nil)
	if err != nil {
		t.Fatalf("connect server: %v", err)
	}
	defer serverSession.Close()

	clientSession, err := client.Connect(ctx, clientTransport, nil)
	if err != nil {
		t.Fatalf("connect client: %v", err)
	}
	defer clientSession.Close()

	result, err := clientSession.ListTools(ctx, nil)
	if err != nil {
		t.Fatalf("list tools: %v", err)
	}
	if len(result.Tools) != 1 {
		t.Fatalf("expected one tool, got %d", len(result.Tools))
	}
	if result.Tools[0].Name != "update_product_price" {
		t.Fatalf("unexpected tool: %q", result.Tools[0].Name)
	}
}
