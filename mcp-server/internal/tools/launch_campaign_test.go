package tools

import (
	"context"
	"testing"
)

type fakeCampaignLauncher struct {
	output LaunchCampaignOutput
	err    error
	calls  int
}

func (fake *fakeCampaignLauncher) ExecuteCampaignLaunch(
	_ context.Context,
	_ LaunchCampaignInput,
) (LaunchCampaignOutput, error) {
	fake.calls++
	return fake.output, fake.err
}

func validCampaignInput() LaunchCampaignInput {
	return LaunchCampaignInput{
		ActionID:             "3bcbd5d7-49ab-4593-8e8d-f99636690519",
		IdempotencyKey:       "campaign-launch:3bcbd5d7",
		DraftID:              "3bcbd5d7-49ab-4593-8e8d-f99636690519",
		SKU:                  "NOVA-AUDIO-001",
		SourceCatalogVersion: 3,
		SourcePrice:          "99.99",
	}
}

func TestLaunchCampaignToolSuccess(t *testing.T) {
	t.Parallel()

	launcher := &fakeCampaignLauncher{output: LaunchCampaignOutput{
		Status:   "executed",
		ActionID: validCampaignInput().ActionID,
		DraftID:  validCampaignInput().DraftID,
		SKU:      validCampaignInput().SKU,
	}}
	tool := NewLaunchCampaignTool(launcher)

	result, output, err := tool.Handle(
		context.Background(),
		nil,
		validCampaignInput(),
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != nil {
		t.Fatalf("expected nil protocol result, got %#v", result)
	}
	if output.Status != "executed" {
		t.Fatalf("expected executed status, got %q", output.Status)
	}
	if launcher.calls != 1 {
		t.Fatalf("expected one launcher call, got %d", launcher.calls)
	}
}

func TestLaunchCampaignToolRejectsInvalidInput(t *testing.T) {
	t.Parallel()

	launcher := &fakeCampaignLauncher{}
	tool := NewLaunchCampaignTool(launcher)
	input := validCampaignInput()
	input.SourceCatalogVersion = 0

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
	if launcher.calls != 0 {
		t.Fatalf("launcher should not run, got %d calls", launcher.calls)
	}
}

func TestLaunchCampaignToolMapsStaleCampaign(t *testing.T) {
	t.Parallel()

	launcher := &fakeCampaignLauncher{err: ErrStaleCampaign}
	tool := NewLaunchCampaignTool(launcher)

	result, output, err := tool.Handle(
		context.Background(),
		nil,
		validCampaignInput(),
	)
	if err != nil {
		t.Fatalf("unexpected protocol error: %v", err)
	}
	if result == nil || !result.IsError {
		t.Fatal("expected MCP tool error result")
	}
	if output.ErrorCode != "stale_campaign" {
		t.Fatalf("expected stale_campaign, got %q", output.ErrorCode)
	}
}
