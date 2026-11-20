package tools

import (
	"context"
	"errors"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

var (
	ErrCampaignDraftNotFound = errors.New("campaign draft not found")
	ErrStaleCampaign         = errors.New("campaign source state changed after approval")
)

type LaunchCampaignInput struct {
	ActionID             string `json:"action_id" jsonschema:"UUID of the approved CommercePilot action"`
	IdempotencyKey       string `json:"idempotency_key" jsonschema:"Unique key preventing duplicate launch"`
	DraftID              string `json:"draft_id" jsonschema:"UUID of the approved campaign draft"`
	SKU                  string `json:"sku" jsonschema:"NovaCart product SKU"`
	SourceCatalogVersion int    `json:"source_catalog_version" jsonschema:"Catalog version on which approval was based"`
	SourcePrice          string `json:"source_price" jsonschema:"Product price on which approval was based"`
}

type LaunchCampaignOutput struct {
	Status     string `json:"status"`
	ActionID   string `json:"action_id"`
	DraftID    string `json:"draft_id"`
	SKU        string `json:"sku"`
	LaunchedAt string `json:"launched_at,omitempty"`
	Replayed   bool   `json:"replayed"`
	ErrorCode  string `json:"error_code,omitempty"`
	Message    string `json:"message,omitempty"`
}

type CampaignLauncher interface {
	ExecuteCampaignLaunch(
		context.Context,
		LaunchCampaignInput,
	) (LaunchCampaignOutput, error)
}

type LaunchCampaignTool struct {
	launcher CampaignLauncher
}

func NewLaunchCampaignTool(launcher CampaignLauncher) *LaunchCampaignTool {
	return &LaunchCampaignTool{launcher: launcher}
}

func (tool *LaunchCampaignTool) Handle(
	ctx context.Context,
	_ *mcp.CallToolRequest,
	input LaunchCampaignInput,
) (*mcp.CallToolResult, LaunchCampaignOutput, error) {
	if strings.TrimSpace(input.ActionID) == "" ||
		strings.TrimSpace(input.IdempotencyKey) == "" ||
		strings.TrimSpace(input.DraftID) == "" ||
		strings.TrimSpace(input.SKU) == "" ||
		input.SourceCatalogVersion < 1 ||
		strings.TrimSpace(input.SourcePrice) == "" {
		return &mcp.CallToolResult{IsError: true}, LaunchCampaignOutput{
			Status:    "rejected",
			ActionID:  input.ActionID,
			DraftID:   input.DraftID,
			SKU:       input.SKU,
			ErrorCode: "invalid_input",
			Message:   ErrInvalidInput.Error(),
		}, nil
	}

	output, err := tool.launcher.ExecuteCampaignLaunch(ctx, input)
	if err == nil {
		return nil, output, nil
	}
	return &mcp.CallToolResult{IsError: true}, LaunchCampaignOutput{
		Status:    "rejected",
		ActionID:  input.ActionID,
		DraftID:   input.DraftID,
		SKU:       input.SKU,
		ErrorCode: classifyError(err),
		Message:   err.Error(),
	}, nil
}
