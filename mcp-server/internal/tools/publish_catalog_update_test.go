package tools

import (
	"context"
	"testing"
)

type fakeCatalogPublisher struct {
	output PublishCatalogUpdateOutput
	err    error
	calls  int
}

func (fake *fakeCatalogPublisher) ExecuteCatalogPublish(
	_ context.Context,
	_ PublishCatalogUpdateInput,
) (PublishCatalogUpdateOutput, error) {
	fake.calls++
	return fake.output, fake.err
}

func validCatalogInput() PublishCatalogUpdateInput {
	return PublishCatalogUpdateInput{
		ActionID:               "af2bc39c-6b34-45f8-9f7a-d9e2932e03dc",
		IdempotencyKey:         "catalog-publish:af2bc39c",
		DraftID:                "af2bc39c-6b34-45f8-9f7a-d9e2932e03dc",
		SKU:                    "NOVA-AUDIO-001",
		ExpectedCatalogVersion: 1,
	}
}

func TestPublishCatalogUpdateToolSuccess(t *testing.T) {
	t.Parallel()

	publisher := &fakeCatalogPublisher{output: PublishCatalogUpdateOutput{
		Status:                "executed",
		ActionID:              validCatalogInput().ActionID,
		DraftID:               validCatalogInput().DraftID,
		SKU:                   validCatalogInput().SKU,
		CurrentCatalogVersion: 2,
	}}
	tool := NewPublishCatalogUpdateTool(publisher)

	result, output, err := tool.Handle(
		context.Background(),
		nil,
		validCatalogInput(),
	)

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != nil {
		t.Fatalf("expected nil protocol result, got %#v", result)
	}
	if output.CurrentCatalogVersion != 2 {
		t.Fatalf("expected catalog version 2, got %d", output.CurrentCatalogVersion)
	}
	if publisher.calls != 1 {
		t.Fatalf("expected one publisher call, got %d", publisher.calls)
	}
}

func TestPublishCatalogUpdateToolRejectsInvalidVersion(t *testing.T) {
	t.Parallel()

	publisher := &fakeCatalogPublisher{}
	tool := NewPublishCatalogUpdateTool(publisher)
	input := validCatalogInput()
	input.ExpectedCatalogVersion = 0

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
	if publisher.calls != 0 {
		t.Fatalf("publisher should not run, got %d calls", publisher.calls)
	}
}

func TestPublishCatalogUpdateToolMapsStaleCatalog(t *testing.T) {
	t.Parallel()

	publisher := &fakeCatalogPublisher{err: ErrStaleCatalog}
	tool := NewPublishCatalogUpdateTool(publisher)

	result, output, err := tool.Handle(
		context.Background(),
		nil,
		validCatalogInput(),
	)

	if err != nil {
		t.Fatalf("unexpected protocol error: %v", err)
	}
	if result == nil || !result.IsError {
		t.Fatal("expected MCP tool error result")
	}
	if output.ErrorCode != "stale_catalog" {
		t.Fatalf("expected stale_catalog, got %q", output.ErrorCode)
	}
}
