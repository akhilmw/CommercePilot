# CommercePilot

CommercePilot is a portfolio-focused multi-agent ecommerce intelligence platform.
It coordinates customer-review analysis, competitor-price intelligence, catalog
optimization, and campaign generation through LangGraph. A Go MCP server exposes
controlled commerce tools, while every publishing action requires human approval.

## Current status

Week 1 foundation: repository scaffolding and service health checks.

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

Start PostgreSQL:

```bash
make db-up
```

Run each application in its own terminal:

```bash
make api
make go-server
make web
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

The project intentionally begins with health checks only. Domain models, MCP tools,
LangGraph agents, and publishing workflows will be implemented incrementally.

