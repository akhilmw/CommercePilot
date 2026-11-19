package tools

import (
	"context"
	"errors"
	"testing"
)

type fakePriceUpdater struct {
	output UpdateProductPriceOutput
	err    error
	calls  int
}

func (fake *fakePriceUpdater) ExecutePriceUpdate(
	_ context.Context,
	_ UpdateProductPriceInput,
) (UpdateProductPriceOutput, error) {
	fake.calls++
	return fake.output, fake.err
}

func validInput() UpdateProductPriceInput {
	return UpdateProductPriceInput{
		ActionID:             "af2bc39c-6b34-45f8-9f7a-d9e2932e03dc",
		IdempotencyKey:       "price-change-test-001",
		SKU:                  "NOVA-AUDIO-001",
		ExpectedCurrentPrice: "129.99",
		NewPrice:             "119.99",
	}
}

func TestUpdateProductPriceToolSuccess(t *testing.T) {
	t.Parallel()

	updater := &fakePriceUpdater{output: UpdateProductPriceOutput{
		Status:       "executed",
		ActionID:     validInput().ActionID,
		SKU:          validInput().SKU,
		CurrentPrice: "119.99",
	}}
	tool := NewUpdateProductPriceTool(updater)

	result, output, err := tool.Handle(context.Background(), nil, validInput())

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != nil {
		t.Fatalf("expected nil protocol result, got %#v", result)
	}
	if output.Status != "executed" {
		t.Fatalf("expected executed output, got %q", output.Status)
	}
	if updater.calls != 1 {
		t.Fatalf("expected one updater call, got %d", updater.calls)
	}
}

func TestUpdateProductPriceToolRejectsMissingInput(t *testing.T) {
	t.Parallel()

	updater := &fakePriceUpdater{}
	tool := NewUpdateProductPriceTool(updater)
	input := validInput()
	input.ActionID = ""

	result, output, err := tool.Handle(context.Background(), nil, input)

	if err != nil {
		t.Fatalf("unexpected protocol error: %v", err)
	}
	if result == nil || !result.IsError {
		t.Fatal("expected MCP tool error result")
	}
	if output.ErrorCode != "invalid_input" {
		t.Fatalf("expected invalid_input, got %q", output.ErrorCode)
	}
	if updater.calls != 0 {
		t.Fatalf("updater should not run, got %d calls", updater.calls)
	}
}

func TestUpdateProductPriceToolMapsApprovalFailure(t *testing.T) {
	t.Parallel()

	updater := &fakePriceUpdater{err: ErrApprovalMismatch}
	tool := NewUpdateProductPriceTool(updater)

	result, output, err := tool.Handle(context.Background(), nil, validInput())

	if err != nil {
		t.Fatalf("unexpected protocol error: %v", err)
	}
	if result == nil || !result.IsError {
		t.Fatal("expected MCP tool error result")
	}
	if output.ErrorCode != "approval_mismatch" {
		t.Fatalf("expected approval_mismatch, got %q", output.ErrorCode)
	}
	if !errors.Is(updater.err, ErrApprovalMismatch) {
		t.Fatal("expected approval mismatch error")
	}
}
