package tools

import (
	"context"
	"errors"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

var (
	ErrCatalogDraftNotFound = errors.New("catalog draft not found")
	ErrStaleCatalog         = errors.New("product catalog changed after approval")
)

type PublishCatalogUpdateInput struct {
	ActionID               string `json:"action_id" jsonschema:"UUID of the approved CommercePilot action"`
	IdempotencyKey         string `json:"idempotency_key" jsonschema:"Unique key preventing duplicate execution"`
	DraftID                string `json:"draft_id" jsonschema:"UUID of the approved catalog draft"`
	SKU                    string `json:"sku" jsonschema:"NovaCart product SKU"`
	ExpectedCatalogVersion int    `json:"expected_catalog_version" jsonschema:"Catalog version on which approval was based"`
}

type PublishCatalogUpdateOutput struct {
	Status                 string `json:"status"`
	ActionID               string `json:"action_id"`
	DraftID                string `json:"draft_id"`
	SKU                    string `json:"sku"`
	PreviousCatalogVersion int    `json:"previous_catalog_version,omitempty"`
	CurrentCatalogVersion  int    `json:"current_catalog_version,omitempty"`
	PublishedAt            string `json:"published_at,omitempty"`
	Replayed               bool   `json:"replayed"`
	ErrorCode              string `json:"error_code,omitempty"`
	Message                string `json:"message,omitempty"`
}

type CatalogPublisher interface {
	ExecuteCatalogPublish(
		context.Context,
		PublishCatalogUpdateInput,
	) (PublishCatalogUpdateOutput, error)
}

type PublishCatalogUpdateTool struct {
	publisher CatalogPublisher
}

func NewPublishCatalogUpdateTool(
	publisher CatalogPublisher,
) *PublishCatalogUpdateTool {
	return &PublishCatalogUpdateTool{publisher: publisher}
}

func (tool *PublishCatalogUpdateTool) Handle(
	ctx context.Context,
	_ *mcp.CallToolRequest,
	input PublishCatalogUpdateInput,
) (*mcp.CallToolResult, PublishCatalogUpdateOutput, error) {
	if strings.TrimSpace(input.ActionID) == "" ||
		strings.TrimSpace(input.IdempotencyKey) == "" ||
		strings.TrimSpace(input.DraftID) == "" ||
		strings.TrimSpace(input.SKU) == "" ||
		input.ExpectedCatalogVersion < 1 {
		return &mcp.CallToolResult{IsError: true}, PublishCatalogUpdateOutput{
			Status:    "rejected",
			ActionID:  input.ActionID,
			DraftID:   input.DraftID,
			SKU:       input.SKU,
			ErrorCode: "invalid_input",
			Message:   ErrInvalidInput.Error(),
		}, nil
	}

	output, err := tool.publisher.ExecuteCatalogPublish(ctx, input)
	if err == nil {
		return nil, output, nil
	}

	return &mcp.CallToolResult{IsError: true}, PublishCatalogUpdateOutput{
		Status:    "rejected",
		ActionID:  input.ActionID,
		DraftID:   input.DraftID,
		SKU:       input.SKU,
		ErrorCode: classifyError(err),
		Message:   err.Error(),
	}, nil
}
