# CommercePilot

CommercePilot is a multi-agent operations dashboard for a simulated ecommerce
store. Choose a product, run an intelligence cycle, and review what the system
recommends based on customer feedback and competitor pricing. Agents can draft
changes. A human decides whether to publish catalog copy, launch a campaign,
or change a price.

**[Try the live read-only demo](https://commercepilot-akhil.duckdns.org/).**
Select **NovaSound Pro → View run history → Run 7E14312C** to replay a
completed cycle with catalog, campaign, and price-change approvals.

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-1C3C3C)
![React](https://img.shields.io/badge/UI-React-087EA4)
![Go MCP](https://img.shields.io/badge/Tools-Go%20%2B%20MCP-00ADD8)

## Demo video

[![Play the CommercePilot demo on YouTube](https://i.ytimg.com/vi/d33EuCwaCGU/hqdefault.jpg)](https://youtu.be/d33EuCwaCGU)

[Watch the CommercePilot demo on YouTube](https://youtu.be/d33EuCwaCGU)

## What you can do

- **Inspect a product.** Browse three demo products, their review counts, mapped competitors, price history, and previous runs.
- **Simulate a market change.** Append a competitor price snapshot and run a new cycle to see how the price change affects the strategy.
- **Review proposals before execution.** Compare catalog fields side by side, preview campaign assets, and approve or decline governed actions from the run workspace.
- **Follow a run.** See stage durations, input and output token counts, estimated model cost, failure reasons, and approval decisions.
- **Evaluate the agents.** Run 30 scenarios covering evidence attribution, competitor coverage, strategy routing, content generation, and approval policy.

The included NovaCart data is synthetic. Campaign launch marks the approved
campaign as launched in the local database. The demo operates without email or
advertising platform integrations.

## Architecture

~~~mermaid
flowchart LR
    UI["React dashboard and Nginx"] -->|"REST and polling"| API["FastAPI"]
    API -->|"Create runs and record decisions"| DB[("PostgreSQL")]
    Worker["Python worker and LangGraph"] <-->|"Claim jobs, save state and checkpoints"| DB
    Worker -->|"Structured generation and verification"| LLM["OpenAI Responses API"]
    Worker -->|"Approved actions over MCP"| Go["Go MCP server"]
    Go -->|"Transactional writes and audit results"| DB
~~~

FastAPI accepts a run request and writes a pending job. A separate Python worker
claims the job and runs the graph. Review and competitor analyses run in
parallel and feed strategy synthesis. The graph then drafts any required
catalog and campaign updates and pauses at approval checkpoints.

If a campaign requires a catalog that has never been published, the graph
starts with a catalog draft and requests catalog approval first. After a
successful publication it can draft the campaign. Declining the prerequisite
skips that campaign. Campaign launch and price changes have their own approval
steps.

The [architecture guide](docs/architecture.md) includes the detailed service
map, workflow branches, approval and resume sequence, data ownership, and
operational tradeoffs.

## Run locally

You need Docker with Compose and an OpenAI API key for live agent runs.
From the repository root:

~~~bash
cp .env.example .env
# Set COMMERCEPILOT_OPENAI_API_KEY in .env before running agents.
docker compose up -d --build --wait
docker compose exec -T api python scripts/seed_catalog.py
docker compose exec -T api python scripts/seed_reviews.py
~~~

Compose starts PostgreSQL, runs Alembic migrations, and starts the MCP server,
API, worker, and dashboard. The seed commands load the demo products, mapped
competitors, initial snapshots, and customer reviews. The dashboard can be
explored with seed data even before you configure model access.

| Service | Local address |
| --- | --- |
| React dashboard | [localhost:5173](http://localhost:5173) |
| FastAPI OpenAPI docs | [localhost:8000/docs](http://localhost:8000/docs) |
| FastAPI health | [localhost:8000/health](http://localhost:8000/health) |
| Go MCP health | [localhost:8081/health](http://localhost:8081/health) |

The Compose demo is intended for local development. Keep `.env` out of version control.
Model calls use your configured OpenAI account and can incur usage charges.

### Walk through a demo

1. Open **Products**, select **NovaBrew Pro** (`NOVA-HOME-001`), and start an intelligence cycle. The strategy determines which actions to propose, so the exact path varies by run.
2. Open **Agent runs** to follow the timeline. When a draft needs approval, compare the proposed catalog fields or review the campaign preview before deciding.
3. Open **Market simulator**, record a new snapshot for a mapped competitor, and run another cycle for the same product to compare the resulting recommendations.

The other seeded products are **NovaSound Pro** (`NOVA-AUDIO-001`) and
**NovaFit Watch** (`NOVA-WEAR-001`).

To request both draft stages explicitly for a demonstration:

~~~bash
curl -fsS http://localhost:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"product_sku":"NOVA-HOME-001","force_catalog_update":true,"force_campaign_update":true}'
~~~

The request queues work and returns a run ID. The flags select draft stages
while the usual approval checks still govern execution. Use
`GET /api/runs/{run_id}/timeline` to read the audit trail or
`docker compose logs -f worker` to follow the worker.

### Configuration

| Variable | Purpose |
| --- | --- |
| `COMMERCEPILOT_OPENAI_API_KEY` | API key used for live generation and verification |
| `COMMERCEPILOT_OPENAI_MODEL` | Configured model, with `gpt-5-mini` as the repository default |
| `COMMERCEPILOT_READ_ONLY_DEMO` | Blocks API writes and enables saved-run replay in the web UI |
| `COMMERCEPILOT_DATABASE_URL` | SQLAlchemy connection for host-run Python processes |
| `COMMERCEPILOT_MCP_BASE_URL` | Go tool server address for host-run Python processes |
| `COMMERCEPILOT_MCP_DATABASE_URL` | PostgreSQL address for the Go server when run on the host |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local Compose database settings |
| `VITE_API_BASE_URL` | API base URL for a separate Vite development instance |

Compose injects container-network database and MCP addresses. The bundled
dashboard proxies `/api/` through Nginx, so the browser uses the dashboard's
origin.

### Preview the public demo

Complete a run with catalog and campaign approvals in your local stack. Then
start the same stack with `COMMERCEPILOT_READ_ONLY_DEMO=true` and refresh the
dashboard. The API rejects write requests and the UI shows saved timelines,
catalog diffs, and campaign previews. To return to local operator mode, start
the stack with `COMMERCEPILOT_READ_ONLY_DEMO=false`.

Use only synthetic data and demo approval comments in a public database.
The [GCP deployment guide](docs/deployment.md) describes the separate public
and operator entry points. Only the private API can queue work for the worker.

## Evaluation and verification

The suite contains six review, six competitor, six strategy, six catalog, two
campaign, and four governance scenarios. It scores outputs against seeded
evidence and routing expectations. Related scenarios reuse agent outputs within
a run. Governance checks use deterministic inputs, and the suite leaves product
prices, catalogs, and campaign status unchanged.

| Recorded verification | Result |
| --- | --- |
| Full 30-scenario baseline | 28/30 passed (93%). Both failures were NovaFit catalog cases. |
| Focused rerun after catalog fixes | 2/2 NovaFit cases passed. |
| Local NovaBrew workflow smoke test | Catalog version 1 → 2 and campaign launch recorded after separate approvals. |

The focused rerun verified the two earlier failures on the corrected code.
These results were collected across two evaluation runs. The live smoke test
used explicit catalog drafting.

~~~bash
docker compose exec -T api python scripts/evaluate_agents.py \
  --case review-novafit-core-themes \
  --case strategy-novafit-grounding

# Run the full suite from the host to keep the JSON report in your checkout.
uv sync --locked
uv run python scripts/evaluate_agents.py --output artifacts/evaluations/baseline.json
~~~

Use an already seeded database and configured model access. JSON reports include
the model, per-case timings and checks, and summary statistics. Case timings can
include upstream calls or reuse cached results, so they describe the evaluation
run rather than independent request latency.

### Quality checks

For host development, install Python and frontend dependencies with
`make install`. Then run `make lint` and `make test`. CI runs Ruff, Pyright,
pytest, Go tests and vet, and the React production build. Live model
evaluations run separately.

## Repository layout

~~~
src/commercepilot/  FastAPI routes, typed models, LangGraph, and services
mcp-server/         Go MCP server, commerce tools, and PostgreSQL transactions
web/                React dashboard, Vite development, and Nginx config
alembic/            Database migrations
scripts/            Seeders, worker entry point, and evaluation CLI
tests/              Python unit and workflow tests
docs/               Detailed architecture and operational notes
~~~

CommercePilot is designed for local portfolio demonstrations. Before hosting
it for multiple users, add authenticated access and reviewer identity, restrict
network access to PostgreSQL and MCP, and define worker recovery and budget
controls.
