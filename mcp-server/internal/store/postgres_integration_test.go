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
		ActionID:             actionID,
		IdempotencyKey:       idempotencyKey,
		SKU:                  "NOVA-AUDIO-001",
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

func TestCatalogPayloadMatchesApprovedIdentifiers(t *testing.T) {
	t.Parallel()

	payload := catalogPublishPayload{
		DraftID:                "draft-001",
		ProductSKU:             "NOVA-AUDIO-001",
		ExpectedCatalogVersion: 3,
	}
	input := tools.PublishCatalogUpdateInput{
		DraftID:                "draft-001",
		SKU:                    "NOVA-AUDIO-001",
		ExpectedCatalogVersion: 3,
	}

	if !catalogPayloadMatches(payload, input) {
		t.Fatal("expected approved catalog identifiers to match")
	}

	input.ExpectedCatalogVersion = 4
	if catalogPayloadMatches(payload, input) {
		t.Fatal("expected changed catalog version to be rejected")
	}
}

func TestExecuteCatalogPublishIntegration(t *testing.T) {
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

	var productID string
	var draftID string
	if err := pool.QueryRow(
		ctx,
		"SELECT gen_random_uuid()::text, gen_random_uuid()::text",
	).Scan(&productID, &draftID); err != nil {
		t.Fatalf("create integration IDs: %v", err)
	}
	sku := "TEST-CATALOG-" + draftID[:8]
	if _, err := pool.Exec(
		ctx,
		`INSERT INTO products (
			id, sku, name, category, description, specifications,
			price, currency, status, catalog_version
		 ) VALUES (
			$1, $2, 'Catalog Test Product', 'test-category',
			'Original catalog description.', '{}'::jsonb,
			10.00, 'USD', 'active', 1
		 )`,
		productID,
		sku,
	); err != nil {
		t.Fatalf("insert test product: %v", err)
	}
	defer func() {
		_, _ = pool.Exec(ctx, "DELETE FROM approved_actions WHERE id = $1", draftID)
		_, _ = pool.Exec(ctx, "DELETE FROM products WHERE id = $1", productID)
	}()

	featureBullets := json.RawMessage(
		`[{"text":"Evidence-backed catalog bullet.","evidence_ids":[]}]`,
	)
	seoKeywords := json.RawMessage(`["catalog test","wireless test"]`)
	_, err = pool.Exec(
		ctx,
		`INSERT INTO catalog_drafts (
			id, product_id, expected_catalog_version,
			seo_title, meta_description, product_description,
			feature_bullets, seo_keywords, target_audience,
			supporting_evidence_ids, confidence, status, approved_at
		 ) VALUES (
			$1, $2, 1,
			'Approved Catalog Test Title',
			'Approved catalog metadata for an isolated integration test product.',
			'Approved catalog description applied only to a temporary test product.',
			$3::jsonb, $4::jsonb, 'Integration test customers',
			'[]'::jsonb, 0.900, 'approved', now()
		 )`,
		draftID,
		productID,
		featureBullets,
		seoKeywords,
	)
	if err != nil {
		t.Fatalf("insert approved catalog draft: %v", err)
	}

	idempotencyKey := "catalog-publish:" + draftID
	payload, err := json.Marshal(catalogPublishPayload{
		DraftID:                draftID,
		ProductID:              productID,
		ProductSKU:             sku,
		ExpectedCatalogVersion: 1,
		SEOTitle:               "Approved Catalog Test Title",
		MetaDescription:        "Approved catalog metadata for an isolated integration test product.",
		ProductDescription:     "Approved catalog description applied only to a temporary test product.",
		FeatureBullets:         featureBullets,
		SEOKeywords:            seoKeywords,
		TargetAudience:         "Integration test customers",
	})
	if err != nil {
		t.Fatalf("encode approved catalog payload: %v", err)
	}
	_, err = pool.Exec(
		ctx,
		`INSERT INTO approved_actions (
			id, action_type, idempotency_key, payload,
			status, approved_by, approved_at
		 ) VALUES (
			$1, 'publish_catalog_update', $2, $3::jsonb,
			'approved', 'integration-test', now()
		 )`,
		draftID,
		idempotencyKey,
		payload,
	)
	if err != nil {
		t.Fatalf("insert approved catalog action: %v", err)
	}

	repository := New(pool)
	input := tools.PublishCatalogUpdateInput{
		ActionID:               draftID,
		IdempotencyKey:         idempotencyKey,
		DraftID:                draftID,
		SKU:                    sku,
		ExpectedCatalogVersion: 1,
	}
	first, err := repository.ExecuteCatalogPublish(ctx, input)
	if err != nil {
		t.Fatalf("publish approved catalog: %v", err)
	}
	if first.Status != "executed" || first.CurrentCatalogVersion != 2 || first.Replayed {
		t.Fatalf("unexpected first result: %#v", first)
	}

	second, err := repository.ExecuteCatalogPublish(ctx, input)
	if err != nil {
		t.Fatalf("replay catalog publication: %v", err)
	}
	if !second.Replayed {
		t.Fatalf("expected replayed result, got %#v", second)
	}

	var catalogVersion int
	var seoTitle string
	var draftStatus string
	var actionStatus string
	if err := pool.QueryRow(
		ctx,
		`SELECT p.catalog_version, p.seo_title, d.status, a.status
		 FROM products p
		 JOIN catalog_drafts d ON d.product_id = p.id
		 JOIN approved_actions a ON a.id = d.id
		 WHERE p.id = $1 AND d.id = $2`,
		productID,
		draftID,
	).Scan(
		&catalogVersion,
		&seoTitle,
		&draftStatus,
		&actionStatus,
	); err != nil {
		t.Fatalf("load published catalog state: %v", err)
	}
	if catalogVersion != 2 || seoTitle != "Approved Catalog Test Title" {
		t.Fatalf("unexpected product catalog state: version=%d title=%q", catalogVersion, seoTitle)
	}
	if draftStatus != "published" || actionStatus != "executed" {
		t.Fatalf("unexpected lifecycle state: draft=%q action=%q", draftStatus, actionStatus)
	}
}
