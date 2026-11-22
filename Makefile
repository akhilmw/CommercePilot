.PHONY: install api go-server web up up-detached down logs db-up db-down test lint

install:
	uv sync
	cd web && npm install

api:
	uv run uvicorn commercepilot.main:app --reload --port 8000

go-server:
	cd mcp-server && go run ./cmd/server

web:
	cd web && npm run dev

up:
	docker compose up --build

up-detached:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker mcp web

db-up:
	docker compose up -d db

db-down:
	docker compose down

test:
	uv run pytest
	cd mcp-server && go test ./...
	cd web && npm run build

lint:
	uv run ruff check .
	uv run pyright
	cd mcp-server && go vet ./...

