# CommercePilot

CommercePilot is a portfolio-focused multi-agent ecommerce intelligence platform.
It coordinates customer-review analysis, competitor-price intelligence, catalog
optimization, and campaign generation through LangGraph. A Go MCP server exposes
controlled commerce tools, while every publishing action requires human approval.

## Current status

CommercePilot currently includes three seeded products, persistent orchestration
runs, human approval workflows, catalog and campaign agents, a Go MCP tool server,
and a React operations dashboard. A 30-scenario evaluation suite measures agent
grounding, competitive analysis, routing, approval policy, and generated content.

## Architecture

```text
React UI -> FastAPI + LangGraph -> MCP client -> Go MCP server -> PostgreSQL
```

## Repository layout

```text
src/commercepilot/       Python API and agent workflow
tests/                   Python tests
mcp-server/              Go tool service
web/                     React application
docs/                    Architecture and engineering notes
scripts/                 Local utility scripts
```

## Local setup

Copy the environment template before running the services:

```bash
cp .env.example .env
```

Install Python and frontend dependencies:

```bash
make install
```

Start the complete stack:

```bash
docker compose up -d --build
```

Seed the demo catalog and reviews:

```bash
uv run python scripts/seed_catalog.py
uv run python scripts/seed_reviews.py
```

Health endpoints:

- Python API: `http://localhost:8000/health`
- Go service: `http://localhost:8081/health`
- React UI: `http://localhost:5173`

## Quality checks

```bash
make lint
make test
```

## Agent evaluations

Run all 30 controlled scenarios:

```bash
uv run python scripts/evaluate_agents.py
```

Run selected scenarios while iterating on one agent:

```bash
uv run python scripts/evaluate_agents.py \
  --case review-novafit-core-themes \
  --case strategy-novafit-grounding
```

Reports are written to `artifacts/evaluations/` and include per-check results,
case latency, aggregate pass rate, and model configuration. Evaluation calls use
a bounded request timeout and cache shared agent outputs within each run. The
evaluation path never publishes catalog changes, launches campaigns, or changes
product prices.

