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

func normalizedPrice(value string) string {
	price, err := decimal.NewFromString(value)
	if err != nil {
		return value
	}
	return price.StringFixed(2)
}
