package store

import (
	"context"
	"encoding/json"
	"os"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/akhilmw/commercepilot/mcp-server/internal/tools"
)

func TestExecutePriceUpdateIntegration(t *testing.T) {
	databaseURL := os.Getenv("COMMERCEPILOT_TEST_DATABASE_URL")
	if databaseURL == "" {
		t.Skip("COMMERCEPILOT_TEST_DATABASE_URL is not configured")
	}

	ctx := context.Background()
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		t.Fatalf("create database pool: %v", err)
	}
	defer pool.Close()

	var actionID string
	if err := pool.QueryRow(ctx, "SELECT gen_random_uuid()::text").Scan(&actionID); err != nil {
		t.Fatalf("create action ID: %v", err)
	}

	var currentPrice string
	if err := pool.QueryRow(
		ctx,
		"SELECT price::text FROM products WHERE sku = 'NOVA-AUDIO-001'",
	).Scan(&currentPrice); err != nil {
		t.Fatalf("load current product price: %v", err)
	}

	idempotencyKey := "integration-" + actionID
	payload, err := json.Marshal(priceChangePayload{
		SKU:                  "NOVA-AUDIO-001",
		ExpectedCurrentPrice: currentPrice,
		NewPrice:             currentPrice,
	})
	if err != nil {
		t.Fatalf("encode approval payload: %v", err)
	}

	_, err = pool.Exec(
		ctx,
		`INSERT INTO approved_actions (
			id, action_type, idempotency_key, payload,
			status, approved_by, approved_at
		 ) VALUES ($1, 'change_price', $2, $3::jsonb, 'approved', 'integration-test', now())`,
		actionID,
		idempotencyKey,
		payload,
	)
	if err != nil {
		t.Fatalf("insert approved action: %v", err)
	}
	defer func() {
		_, _ = pool.Exec(ctx, "DELETE FROM approved_actions WHERE id = $1", actionID)
	}()

	repository := New(pool)
	input := tools.UpdateProductPriceInput{
		ActionID:            actionID,
		IdempotencyKey:      idempotencyKey,
		SKU:                 "NOVA-AUDIO-001",
		ExpectedCurrentPrice: currentPrice,
		NewPrice:             currentPrice,
	}

	first, err := repository.ExecutePriceUpdate(ctx, input)
	if err != nil {
		t.Fatalf("execute approved update: %v", err)
	}
	if first.Status != "executed" || first.Replayed {
		t.Fatalf("unexpected first result: %#v", first)
	}

	second, err := repository.ExecutePriceUpdate(ctx, input)
	if err != nil {
		t.Fatalf("replay approved update: %v", err)
	}
	if !second.Replayed {
		t.Fatalf("expected replayed result, got %#v", second)
	}

	var status string
	if err := pool.QueryRow(
		ctx,
		"SELECT status FROM approved_actions WHERE id = $1",
		actionID,
	).Scan(&status); err != nil {
		t.Fatalf("load action status: %v", err)
	}
	if status != "executed" {
		t.Fatalf("expected executed status, got %q", status)
	}
}

func TestPayloadMatchesNumericPriceFormatting(t *testing.T) {
	t.Parallel()

	payload := priceChangePayload{
		SKU:                  "NOVA-AUDIO-001",
		ExpectedCurrentPrice: "129.9",
		NewPrice:             "119.990",
	}
	input := tools.UpdateProductPriceInput{
		SKU:                  "NOVA-AUDIO-001",
		ExpectedCurrentPrice: "129.90",
		NewPrice:             "119.99",
	}

	if !payloadMatches(payload, input) {
		t.Fatal("expected numerically equivalent prices to match")
	}
}
