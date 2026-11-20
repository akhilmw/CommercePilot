package store

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/shopspring/decimal"

	"github.com/akhilmw/commercepilot/mcp-server/internal/tools"
)

type Repository struct {
	pool *pgxpool.Pool
}

type approvedAction struct {
	actionType     string
	idempotencyKey string
	payload        []byte
	status         string
	result         []byte
}

type priceChangePayload struct {
	SKU                  string `json:"sku"`
	ExpectedCurrentPrice string `json:"expected_current_price"`
	NewPrice             string `json:"new_price"`
}

type catalogPublishPayload struct {
	DraftID                string          `json:"draft_id"`
	ProductID              string          `json:"product_id"`
	ProductSKU             string          `json:"product_sku"`
	ExpectedCatalogVersion int             `json:"expected_catalog_version"`
	SEOTitle               string          `json:"seo_title"`
	MetaDescription        string          `json:"meta_description"`
	ProductDescription     string          `json:"product_description"`
	FeatureBullets         json.RawMessage `json:"feature_bullets"`
	SEOKeywords            json.RawMessage `json:"seo_keywords"`
	TargetAudience         string          `json:"target_audience"`
}

type campaignLaunchPayload struct {
	DraftID              string          `json:"draft_id"`
	ProductID            string          `json:"product_id"`
	ProductSKU           string          `json:"product_sku"`
	SourceCatalogVersion int             `json:"source_catalog_version"`
	SourcePrice          string          `json:"source_price"`
	Assets               json.RawMessage `json:"assets"`
	SuccessMetrics       json.RawMessage `json:"success_metrics"`
	SupportingEvidence   json.RawMessage `json:"supporting_evidence_ids"`
}

func New(pool *pgxpool.Pool) *Repository {
	return &Repository{pool: pool}
}

func (repository *Repository) ExecutePriceUpdate(
	ctx context.Context,
	input tools.UpdateProductPriceInput,
) (tools.UpdateProductPriceOutput, error) {
	if err := validatePrices(input); err != nil {
		return tools.UpdateProductPriceOutput{}, err
	}

	tx, err := repository.pool.Begin(ctx)
	if err != nil {
		return tools.UpdateProductPriceOutput{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	action, err := loadApprovedAction(ctx, tx, input.ActionID)
	if err != nil {
		return tools.UpdateProductPriceOutput{}, err
	}
	if action.actionType != "change_price" ||
		action.idempotencyKey != input.IdempotencyKey {
		return tools.UpdateProductPriceOutput{}, tools.ErrApprovalMismatch
	}

	if action.status == "executed" {
		var previous tools.UpdateProductPriceOutput
		if len(action.result) == 0 {
			return tools.UpdateProductPriceOutput{}, errors.New("executed action has no stored result")
		}
		if err := json.Unmarshal(action.result, &previous); err != nil {
			return tools.UpdateProductPriceOutput{}, fmt.Errorf("decode stored result: %w", err)
		}
		previous.Replayed = true
		return previous, nil
	}
	if action.status != "approved" {
		return tools.UpdateProductPriceOutput{}, tools.ErrApprovalMismatch
	}

	var approvedPayload priceChangePayload
	if err := json.Unmarshal(action.payload, &approvedPayload); err != nil {
		return tools.UpdateProductPriceOutput{}, fmt.Errorf("decode approved payload: %w", err)
	}
	if !payloadMatches(approvedPayload, input) {
		return tools.UpdateProductPriceOutput{}, tools.ErrApprovalMismatch
	}

	var executedAt time.Time
	err = tx.QueryRow(
		ctx,
		`UPDATE products
		 SET price = $1::numeric, updated_at = now()
		 WHERE sku = $2 AND price = $3::numeric
		 RETURNING updated_at`,
		input.NewPrice,
		input.SKU,
		input.ExpectedCurrentPrice,
	).Scan(&executedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return tools.UpdateProductPriceOutput{}, tools.ErrStalePrice
	}
	if err != nil {
		return tools.UpdateProductPriceOutput{}, fmt.Errorf("update product price: %w", err)
	}

	output := tools.UpdateProductPriceOutput{
		Status:        "executed",
		ActionID:      input.ActionID,
		SKU:           input.SKU,
		PreviousPrice: normalizedPrice(input.ExpectedCurrentPrice),
		CurrentPrice:  normalizedPrice(input.NewPrice),
		ExecutedAt:    executedAt.UTC().Format(time.RFC3339),
		Replayed:      false,
	}
	resultJSON, err := json.Marshal(output)
	if err != nil {
		return tools.UpdateProductPriceOutput{}, fmt.Errorf("encode execution result: %w", err)
	}

	_, err = tx.Exec(
		ctx,
		`UPDATE approved_actions
		 SET status = 'executed', executed_at = $2, result = $3::jsonb
		 WHERE id = $1`,
		input.ActionID,
		executedAt,
		resultJSON,
	)
	if err != nil {
		return tools.UpdateProductPriceOutput{}, fmt.Errorf("record execution result: %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return tools.UpdateProductPriceOutput{}, fmt.Errorf("commit transaction: %w", err)
	}
	return output, nil
}

func (repository *Repository) ExecuteCatalogPublish(
	ctx context.Context,
	input tools.PublishCatalogUpdateInput,
) (tools.PublishCatalogUpdateOutput, error) {
	tx, err := repository.pool.Begin(ctx)
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"begin transaction: %w",
			err,
		)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	action, err := loadApprovedAction(ctx, tx, input.ActionID)
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, err
	}
	if action.actionType != "publish_catalog_update" ||
		action.idempotencyKey != input.IdempotencyKey {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrApprovalMismatch
	}

	if action.status == "executed" {
		var previous tools.PublishCatalogUpdateOutput
		if len(action.result) == 0 {
			return tools.PublishCatalogUpdateOutput{}, errors.New(
				"executed action has no stored result",
			)
		}
		if err := json.Unmarshal(action.result, &previous); err != nil {
			return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
				"decode stored result: %w",
				err,
			)
		}
		previous.Replayed = true
		return previous, nil
	}
	if action.status != "approved" {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrApprovalMismatch
	}

	var approvedPayload catalogPublishPayload
	if err := json.Unmarshal(action.payload, &approvedPayload); err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"decode approved payload: %w",
			err,
		)
	}
	if !catalogPayloadMatches(approvedPayload, input) {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrApprovalMismatch
	}
	if !json.Valid(approvedPayload.FeatureBullets) ||
		!json.Valid(approvedPayload.SEOKeywords) {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrInvalidInput
	}

	var draftProductID string
	var draftExpectedVersion int
	var draftStatus string
	err = tx.QueryRow(
		ctx,
		`SELECT product_id::text, expected_catalog_version, status
		 FROM catalog_drafts
		 WHERE id = $1
		 FOR UPDATE`,
		input.DraftID,
	).Scan(
		&draftProductID,
		&draftExpectedVersion,
		&draftStatus,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrCatalogDraftNotFound
	}
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"load catalog draft: %w",
			err,
		)
	}
	if draftProductID != approvedPayload.ProductID ||
		draftExpectedVersion != input.ExpectedCatalogVersion ||
		draftStatus != "approved" {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrApprovalMismatch
	}

	var currentVersion int
	var publishedAt time.Time
	err = tx.QueryRow(
		ctx,
		`UPDATE products
		 SET seo_title = $1,
		     meta_description = $2,
		     description = $3,
		     feature_bullets = $4::jsonb,
		     seo_keywords = $5::jsonb,
		     target_audience = $6,
		     catalog_version = catalog_version + 1,
		     updated_at = now()
		 WHERE id = $7
		   AND sku = $8
		   AND catalog_version = $9
		 RETURNING catalog_version, updated_at`,
		approvedPayload.SEOTitle,
		approvedPayload.MetaDescription,
		approvedPayload.ProductDescription,
		approvedPayload.FeatureBullets,
		approvedPayload.SEOKeywords,
		approvedPayload.TargetAudience,
		approvedPayload.ProductID,
		input.SKU,
		input.ExpectedCatalogVersion,
	).Scan(&currentVersion, &publishedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return tools.PublishCatalogUpdateOutput{}, tools.ErrStaleCatalog
	}
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"publish product catalog: %w",
			err,
		)
	}

	_, err = tx.Exec(
		ctx,
		`UPDATE catalog_drafts
		 SET status = 'published', published_at = $2, updated_at = $2
		 WHERE id = $1`,
		input.DraftID,
		publishedAt,
	)
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"mark catalog draft published: %w",
			err,
		)
	}

	output := tools.PublishCatalogUpdateOutput{
		Status:                 "executed",
		ActionID:               input.ActionID,
		DraftID:                input.DraftID,
		SKU:                    input.SKU,
		PreviousCatalogVersion: input.ExpectedCatalogVersion,
		CurrentCatalogVersion:  currentVersion,
		PublishedAt:            publishedAt.UTC().Format(time.RFC3339),
		Replayed:               false,
	}
	resultJSON, err := json.Marshal(output)
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"encode execution result: %w",
			err,
		)
	}

	_, err = tx.Exec(
		ctx,
		`UPDATE approved_actions
		 SET status = 'executed', executed_at = $2, result = $3::jsonb
		 WHERE id = $1`,
		input.ActionID,
		publishedAt,
		resultJSON,
	)
	if err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"record execution result: %w",
			err,
		)
	}

	if err := tx.Commit(ctx); err != nil {
		return tools.PublishCatalogUpdateOutput{}, fmt.Errorf(
			"commit transaction: %w",
			err,
		)
	}
	return output, nil
}

func (repository *Repository) ExecuteCampaignLaunch(
	ctx context.Context,
	input tools.LaunchCampaignInput,
) (tools.LaunchCampaignOutput, error) {
	inputPrice, err := decimal.NewFromString(input.SourcePrice)
	if err != nil || inputPrice.IsNegative() {
		return tools.LaunchCampaignOutput{}, tools.ErrInvalidInput
	}

	tx, err := repository.pool.Begin(ctx)
	if err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	action, err := loadApprovedAction(ctx, tx, input.ActionID)
	if err != nil {
		return tools.LaunchCampaignOutput{}, err
	}
	if action.actionType != "launch_campaign" ||
		action.idempotencyKey != input.IdempotencyKey {
		return tools.LaunchCampaignOutput{}, tools.ErrApprovalMismatch
	}
	if action.status == "executed" {
		var previous tools.LaunchCampaignOutput
		if len(action.result) == 0 {
			return tools.LaunchCampaignOutput{}, errors.New("executed action has no stored result")
		}
		if err := json.Unmarshal(action.result, &previous); err != nil {
			return tools.LaunchCampaignOutput{}, fmt.Errorf("decode stored result: %w", err)
		}
		previous.Replayed = true
		return previous, nil
	}
	if action.status != "approved" {
		return tools.LaunchCampaignOutput{}, tools.ErrApprovalMismatch
	}

	var approvedPayload campaignLaunchPayload
	if err := json.Unmarshal(action.payload, &approvedPayload); err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("decode approved payload: %w", err)
	}
	if !campaignPayloadMatches(approvedPayload, input) {
		return tools.LaunchCampaignOutput{}, tools.ErrApprovalMismatch
	}
	if !json.Valid(approvedPayload.Assets) ||
		!json.Valid(approvedPayload.SuccessMetrics) ||
		!json.Valid(approvedPayload.SupportingEvidence) {
		return tools.LaunchCampaignOutput{}, tools.ErrInvalidInput
	}

	var draftProductID string
	var draftCatalogVersion int
	var draftPrice string
	var draftStatus string
	err = tx.QueryRow(
		ctx,
		`SELECT product_id::text, source_catalog_version, source_price::text, status
		 FROM campaign_drafts
		 WHERE id = $1
		 FOR UPDATE`,
		input.DraftID,
	).Scan(&draftProductID, &draftCatalogVersion, &draftPrice, &draftStatus)
	if errors.Is(err, pgx.ErrNoRows) {
		return tools.LaunchCampaignOutput{}, tools.ErrCampaignDraftNotFound
	}
	if err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("load campaign draft: %w", err)
	}
	draftPriceValue, err := decimal.NewFromString(draftPrice)
	if err != nil ||
		draftProductID != approvedPayload.ProductID ||
		draftCatalogVersion != input.SourceCatalogVersion ||
		!draftPriceValue.Equal(inputPrice) ||
		draftStatus != "approved" {
		return tools.LaunchCampaignOutput{}, tools.ErrApprovalMismatch
	}

	var currentCatalogVersion int
	var currentPrice string
	err = tx.QueryRow(
		ctx,
		`SELECT catalog_version, price::text
		 FROM products
		 WHERE id = $1 AND sku = $2
		 FOR UPDATE`,
		approvedPayload.ProductID,
		input.SKU,
	).Scan(&currentCatalogVersion, &currentPrice)
	if errors.Is(err, pgx.ErrNoRows) {
		return tools.LaunchCampaignOutput{}, tools.ErrStaleCampaign
	}
	if err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("load campaign product: %w", err)
	}
	currentPriceValue, err := decimal.NewFromString(currentPrice)
	if err != nil || currentCatalogVersion != input.SourceCatalogVersion ||
		!currentPriceValue.Equal(inputPrice) {
		return tools.LaunchCampaignOutput{}, tools.ErrStaleCampaign
	}

	var launchedAt time.Time
	err = tx.QueryRow(
		ctx,
		`UPDATE campaign_drafts
		 SET status = 'launched', launched_at = now(), updated_at = now()
		 WHERE id = $1 AND status = 'approved'
		 RETURNING launched_at`,
		input.DraftID,
	).Scan(&launchedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return tools.LaunchCampaignOutput{}, tools.ErrApprovalMismatch
	}
	if err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("launch campaign: %w", err)
	}

	output := tools.LaunchCampaignOutput{
		Status:     "executed",
		ActionID:   input.ActionID,
		DraftID:    input.DraftID,
		SKU:        input.SKU,
		LaunchedAt: launchedAt.UTC().Format(time.RFC3339),
		Replayed:   false,
	}
	resultJSON, err := json.Marshal(output)
	if err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("encode execution result: %w", err)
	}
	_, err = tx.Exec(
		ctx,
		`UPDATE approved_actions
		 SET status = 'executed', executed_at = $2, result = $3::jsonb
		 WHERE id = $1`,
		input.ActionID,
		launchedAt,
		resultJSON,
	)
	if err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("record execution result: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return tools.LaunchCampaignOutput{}, fmt.Errorf("commit transaction: %w", err)
	}
	return output, nil
}

func loadApprovedAction(
	ctx context.Context,
	tx pgx.Tx,
	actionID string,
) (approvedAction, error) {
	var action approvedAction
	err := tx.QueryRow(
		ctx,
		`SELECT action_type, idempotency_key, payload, status, result
		 FROM approved_actions
		 WHERE id = $1
		 FOR UPDATE`,
		actionID,
	).Scan(
		&action.actionType,
		&action.idempotencyKey,
		&action.payload,
		&action.status,
		&action.result,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return approvedAction{}, tools.ErrApprovalNotFound
	}
	if err != nil {
		return approvedAction{}, fmt.Errorf("load approved action: %w", err)
	}
	return action, nil
}

func validatePrices(input tools.UpdateProductPriceInput) error {
	expected, err := decimal.NewFromString(input.ExpectedCurrentPrice)
	if err != nil || expected.IsNegative() {
		return tools.ErrInvalidInput
	}
	newPrice, err := decimal.NewFromString(input.NewPrice)
	if err != nil || newPrice.IsNegative() {
		return tools.ErrInvalidInput
	}
	return nil
}

func payloadMatches(
	payload priceChangePayload,
	input tools.UpdateProductPriceInput,
) bool {
	approvedExpected, expectedErr := decimal.NewFromString(payload.ExpectedCurrentPrice)
	inputExpected, inputExpectedErr := decimal.NewFromString(input.ExpectedCurrentPrice)
	approvedNew, newErr := decimal.NewFromString(payload.NewPrice)
	inputNew, inputNewErr := decimal.NewFromString(input.NewPrice)
	if expectedErr != nil || inputExpectedErr != nil || newErr != nil || inputNewErr != nil {
		return false
	}
	return payload.SKU == input.SKU &&
		approvedExpected.Equal(inputExpected) &&
		approvedNew.Equal(inputNew)
}

func catalogPayloadMatches(
	payload catalogPublishPayload,
	input tools.PublishCatalogUpdateInput,
) bool {
	return payload.DraftID == input.DraftID &&
		payload.ProductSKU == input.SKU &&
		payload.ExpectedCatalogVersion == input.ExpectedCatalogVersion
}

func campaignPayloadMatches(
	payload campaignLaunchPayload,
	input tools.LaunchCampaignInput,
) bool {
	payloadPrice, payloadErr := decimal.NewFromString(payload.SourcePrice)
	inputPrice, inputErr := decimal.NewFromString(input.SourcePrice)
	if payloadErr != nil || inputErr != nil {
		return false
	}
	return payload.DraftID == input.DraftID &&
		payload.ProductSKU == input.SKU &&
		payload.SourceCatalogVersion == input.SourceCatalogVersion &&
		payloadPrice.Equal(inputPrice)
}

func normalizedPrice(value string) string {
	price, err := decimal.NewFromString(value)
	if err != nil {
		return value
	}
	return price.StringFixed(2)
}
