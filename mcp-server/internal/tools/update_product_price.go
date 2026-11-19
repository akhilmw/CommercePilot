package tools

import (
	"context"
	"errors"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

var (
	ErrInvalidInput     = errors.New("invalid tool input")
	ErrApprovalNotFound = errors.New("approved action not found")
	ErrApprovalMismatch = errors.New("tool input does not match approved action")
	ErrStalePrice       = errors.New("product price changed after approval")
)

type UpdateProductPriceInput struct {
	ActionID             string `json:"action_id" jsonschema:"UUID of the approved CommercePilot action"`
	IdempotencyKey       string `json:"idempotency_key" jsonschema:"Unique key preventing duplicate execution"`
	SKU                  string `json:"sku" jsonschema:"NovaCart product SKU"`
	ExpectedCurrentPrice string `json:"expected_current_price" jsonschema:"Price on which human approval was based"`
	NewPrice             string `json:"new_price" jsonschema:"Exact human-approved replacement price"`
}

type UpdateProductPriceOutput struct {
	Status        string `json:"status"`
	ActionID      string `json:"action_id"`
	SKU           string `json:"sku"`
	PreviousPrice string `json:"previous_price,omitempty"`
	CurrentPrice  string `json:"current_price,omitempty"`
	ExecutedAt    string `json:"executed_at,omitempty"`
	Replayed      bool   `json:"replayed"`
	ErrorCode     string `json:"error_code,omitempty"`
	Message       string `json:"message,omitempty"`
}

type PriceUpdater interface {
	ExecutePriceUpdate(
		context.Context,
		UpdateProductPriceInput,
	) (UpdateProductPriceOutput, error)
}

type UpdateProductPriceTool struct {
	updater PriceUpdater
}

func NewUpdateProductPriceTool(updater PriceUpdater) *UpdateProductPriceTool {
	return &UpdateProductPriceTool{updater: updater}
}

func (tool *UpdateProductPriceTool) Handle(
	ctx context.Context,
	_ *mcp.CallToolRequest,
	input UpdateProductPriceInput,
) (*mcp.CallToolResult, UpdateProductPriceOutput, error) {
	if strings.TrimSpace(input.ActionID) == "" ||
		strings.TrimSpace(input.IdempotencyKey) == "" ||
		strings.TrimSpace(input.SKU) == "" ||
		strings.TrimSpace(input.ExpectedCurrentPrice) == "" ||
		strings.TrimSpace(input.NewPrice) == "" {
		return &mcp.CallToolResult{IsError: true}, UpdateProductPriceOutput{
			Status:    "rejected",
			ActionID:  input.ActionID,
			SKU:       input.SKU,
			ErrorCode: "invalid_input",
			Message:   ErrInvalidInput.Error(),
		}, nil
	}

	output, err := tool.updater.ExecutePriceUpdate(ctx, input)
	if err == nil {
		return nil, output, nil
	}

	errorOutput := UpdateProductPriceOutput{
		Status:    "rejected",
		ActionID:  input.ActionID,
		SKU:       input.SKU,
		ErrorCode: classifyError(err),
		Message:   err.Error(),
	}
	return &mcp.CallToolResult{IsError: true}, errorOutput, nil
}

func classifyError(err error) string {
	switch {
	case errors.Is(err, ErrInvalidInput):
		return "invalid_input"
	case errors.Is(err, ErrApprovalNotFound):
		return "approval_not_found"
	case errors.Is(err, ErrApprovalMismatch):
		return "approval_mismatch"
	case errors.Is(err, ErrStalePrice):
		return "stale_price"
	default:
		return "execution_failed"
	}
}
