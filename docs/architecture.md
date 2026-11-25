# CommercePilot architecture

CommercePilot runs one intelligence cycle per selected NovaCart SKU. It combines
seeded customer reviews and competitor price snapshots with typed model
outputs. Python owns the workflow and approval policy. Go owns the approved
commerce writes. PostgreSQL holds the data used by both services as well as
the graph checkpoints.

## 1. Runtime topology and data flow

~~~mermaid
flowchart LR
    Operator["Operator"]
    OpenAI["OpenAI Responses API"]

    subgraph Compose["Docker Compose network"]
        subgraph UI["Web container"]
            Nginx["Nginx<br/>host port 5173"]
            React["React portfolio, market simulator,<br/>run timeline and approvals"]
            Nginx -->|"Serves static app"| React
        end

        subgraph Python["Python containers"]
            API["FastAPI<br/>host port 8000"]
            Worker["Worker loop<br/>polls every 2 seconds by default"]
            Graph["LangGraph workflow<br/>typed state per run"]
            Agents["Review, competitor, strategy,<br/>catalog and campaign stages"]
            Usage["Stage telemetry<br/>duration, tokens, estimated cost"]
            Client["Python MCP client"]
            Migrate["One-shot Alembic migration"]
            Worker --> Graph
            Graph --> Agents
            Graph --> Client
            Agents --> Usage
        end

        subgraph Tools["Go MCP container"]
            Go["MCP over Streamable HTTP<br/>/mcp on host port 8081"]
            Registry["update_product_price<br/>publish_catalog_update<br/>launch_campaign"]
            Tx["PostgreSQL transactions<br/>approval match, freshness, replay"]
            Go --> Registry --> Tx
        end

        subgraph PG["PostgreSQL 16 · host port 5432"]
            Runs[("Runs, approvals<br/>and stage events")]
            Checkpoints[("LangGraph<br/>checkpoint tables")]
            Evidence[("Products, reviews, competitors<br/>and price snapshots")]
            Drafts[("Catalog and campaign drafts")]
            Actions[("Approved actions<br/>and execution receipts")]
        end
        Migrate -.->|"Creates application schema"| Runs
        Nginx -->|"Proxies /api/"| API
        API -->|"Creates, reads and requeues runs"| Runs
        API -->|"Portfolio and market simulator"| Evidence
        Worker <-->|"Claims pending runs and stores outcome"| Runs
        Graph <-->|"Persists state by thread ID"| Checkpoints
        Agents -->|"Loads product evidence"| Evidence
        Graph -->|"Persists drafts and previews"| Drafts
        Graph -->|"Persists approved payloads"| Actions
        Usage -->|"Stores stage events"| Runs
        Client -->|"Executes an approved action"| Go
        Tx -->|"Updates catalog fields or price"| Evidence
        Tx -->|"Updates draft status"| Drafts
        Tx -->|"Locks action and saves receipt"| Actions
    end

    Operator -->|"Browser"| Nginx
    React -->|"Same-origin REST requests"| Nginx
    Agents <-->|"Structured output and verification"| OpenAI
~~~

The API writes a pending job and returns a run ID. The worker claims a pending
row with `FOR UPDATE SKIP LOCKED` and then runs inference outside the API
request. PostgreSQL is both the job queue and the persistent store. The UI
polls the API while a run is active and links each approval to its run.

| API route | Role |
| --- | --- |
| `GET /api/products` and `GET /api/products/{sku}/runs` | Product portfolio and run history |
| `GET /api/products/{sku}/market` and `POST /api/products/{sku}/market/snapshots` | Market history and simulated observations |
| `POST /api/runs` | Queue a cycle for one SKU |
| `GET /api/runs/{run_id}` and `GET /api/runs/{run_id}/timeline` | Run result and chronological events |
| `GET /api/approvals` and `GET /api/runs/{run_id}/approvals` | Approval inbox and per-run requests |
| `POST /api/runs/{run_id}/approvals/{approval_id}` | Record a decision and requeue the paused run |

## 2. Agent graph and approval branches

~~~mermaid
flowchart TD
    Start["Claim run for selected SKU"]
    Review["Review Agent<br/>themes, complaints, improvements and review IDs"]
    Competitor["Competitor Agent<br/>snapshot deltas, pressure and snapshot IDs"]
    Strategy["Strategy synthesis<br/>join analyses and validate action proposals"]
    CatalogNeeded{"Explicit catalog draft or campaign<br/>requires a published catalog?"}
    Catalog["Catalog Agent<br/>SEO copy, feature bullets and supporting evidence"]
    Compare["Validate claims, save draft<br/>and compute versioned catalog diff"]
    CatalogApproval{"Catalog publish approval"}
    Publish["Go MCP<br/>publish approved catalog version"]
    CampaignNeeded{"Campaign requested and<br/>catalog prerequisite satisfied?"}
    Campaign["Campaign Agent<br/>grounded email, social and paid-search assets"]
    Preview["Validate claims, save draft<br/>and preview against catalog version and price"]
    CampaignApproval{"Campaign launch approval"}
    Launch["Go MCP<br/>record approved campaign launch"]
    Policy["Apply deterministic action policy"]
    PriceNeeded{"Price change<br/>requires approval?"}
    PriceApproval{"Price change approval"}
    Price["Go MCP<br/>update price from approved payload"]
    End["Record final run result"]

    Start --> Review --> Strategy
    Start --> Competitor --> Strategy
    Strategy --> CatalogNeeded
    CatalogNeeded -->|Yes| Catalog --> Compare --> CatalogApproval
    CatalogNeeded -->|No| CampaignNeeded
    CatalogApproval -->|Approve| Publish --> CampaignNeeded
    CatalogApproval -->|Decline| CampaignNeeded
    CampaignNeeded -->|Yes| Campaign --> Preview --> CampaignApproval
    CampaignNeeded -->|No or prerequisite declined| Policy
    CampaignApproval -->|Approve| Launch --> Policy
    CampaignApproval -->|Decline| Policy
    Policy --> PriceNeeded
    PriceNeeded -->|Yes| PriceApproval
    PriceNeeded -->|No| End
    PriceApproval -->|Approve| Price --> End
    PriceApproval -->|Decline| End
~~~

A failed agent or tool can terminate the run and record a failure, so the graph
above shows the normal execution and decision branches. Once a catalog already
exists, declining an optional catalog update can still allow a campaign to be
drafted from the published version. If the missing catalog was a prerequisite,
declining that publish skips the campaign while independent policy actions can
still proceed.

| Stage | Main inputs | Structured output and validation |
| --- | --- | --- |
| Review | Reviews for the selected SKU | Strengths, complaints, and improvements with review IDs. Evidence IDs must refer to supplied reviews. |
| Competitor | Current product and paired price snapshots | Competitor findings and recommendations. Price changes are derived from stored snapshots. Product and snapshot references are checked. |
| Strategy | Both analyses | Evidence-backed action proposals. Routing and approval requirements are determined in code from typed actions and product readiness. |
| Catalog | Product facts and both analyses | SEO title, meta description, product description, bullets, keywords, and audience. Validates schema, citations, copy quality, and factual claims. A separate model call verifies claim support. |
| Campaign | Published catalog, strategy, and both analyses | Channel-specific assets with evidence and success metrics. Validates copy constraints and evidence, then verifies factual support. Documented complaints constrain positive claims. |

Review and competitor evidence is passed to models as data. Prompts instruct
models to ignore embedded instructions, and typed outputs, citation validation,
review checkpoints, and tool-side checks provide additional controls.

## 3. Durable approval and execution

~~~mermaid
sequenceDiagram
    actor Operator
    participant UI as React dashboard
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Worker as Python worker
    participant Graph as LangGraph
    participant Go as Go MCP server

    Operator->>UI: Run intelligence cycle for a SKU
    UI->>API: POST /api/runs
    API->>DB: Insert pending run and thread ID
    API-->>UI: Return run ID
    Worker->>DB: Claim pending row and mark running
    Worker->>Graph: Invoke graph with thread ID
    Graph->>DB: Persist draft and graph checkpoint
    Graph-->>Worker: Interrupt with approval payload
    Worker->>DB: Save approval request and mark awaiting approval
    UI->>API: Poll timeline and pending approvals
    API-->>UI: Return catalog diff, campaign preview, or action details
    Operator->>UI: Approve or decline
    UI->>API: POST approval decision
    API->>DB: Record decision and requeue the existing run
    Worker->>DB: Claim pending run and load decision
    Worker->>Graph: Resume with Command on the same thread
    alt Approved
        Graph->>DB: Persist approved action and idempotency key
        Graph->>Go: Call governed MCP tool with approved arguments
        Go->>DB: Lock action and validate payload and current state
        Go->>DB: Commit effect and execution receipt together
        Go-->>Graph: Return result or existing receipt on replay
    else Declined
        Graph->>DB: Record draft rejection where applicable
    end
    Graph-->>Worker: Return result or next approval interrupt
    Worker->>DB: Persist final status or next approval
~~~

Approval pauses release the worker. The API stores the decision and requeues
the same run, then the worker resumes the persisted LangGraph thread. Existing
run history retains the reviewer label, comment, and request and decision
timestamps. In this local demo the reviewer label is application data. A hosted
deployment should bind decisions to authenticated users.

### Go tool boundaries

| MCP tool | State changed on execution | Stale or mismatched conditions |
| --- | --- | --- |
| `update_product_price` | Product price and approved-action result | Action type, approved arguments, SKU, or price expectation does not match |
| `publish_catalog_update` | Catalog fields and version on the product, draft status, and approved-action result | Draft, approved arguments, or expected catalog version does not match |
| `launch_campaign` | Campaign draft status and launch timestamp, plus approved-action result | Draft, approved arguments, source catalog version, or source price does not match |

The tool service locks the approved-action row, checks the idempotency key, and
validates the operation against the stored approval before a new write.
Business changes and their receipts share a transaction. Repeating a completed
action with its key can return the saved receipt, supporting safe replays at
this boundary. Campaign launch is a local state transition.

## 4. Persistence map

~~~mermaid
erDiagram
    PRODUCTS ||--o{ REVIEWS : receives
    PRODUCTS ||--o{ COMPETITOR_PRODUCTS : maps_to
    COMPETITORS ||--o{ COMPETITOR_PRODUCTS : offers
    COMPETITOR_PRODUCTS ||--o{ COMPETITOR_PRICE_SNAPSHOTS : observed_as
    PRODUCTS ||--o{ ORCHESTRATION_RUNS : analyzed_by
    ORCHESTRATION_RUNS ||--o{ APPROVAL_REQUESTS : requests
    PRODUCTS ||--o{ CATALOG_DRAFTS : described_by
    PRODUCTS ||--o{ CAMPAIGN_DRAFTS : promoted_by
~~~

The diagram shows foreign-key relationships. The run links to LangGraph
checkpoints through its thread ID. Approved actions keep their tool-specific
references in the approved JSON payload. Run stage events live inside the
run record.

| Data | Main tables | How it is used |
| --- | --- | --- |
| Product catalog and prices | `products` | Current product information and catalog version |
| Customer evidence | `reviews` | Product-specific source records for review analysis and evidence references |
| Market evidence | `competitors`, `competitor_products`, `competitor_price_snapshots` | Maps competitor SKUs and stores timestamped price observations |
| Durable jobs and audit history | `orchestration_runs`, `approval_requests` | Run state, results, failure reason, approval payloads and decisions, and agent stage events |
| Graph runtime state | LangGraph PostgreSQL checkpoint tables | Stores graph state keyed by thread ID for interrupt and resume |
| Governance records | `catalog_drafts`, `campaign_drafts`, `approved_actions` | Drafts, expected versions, approved parameters, idempotency keys and receipts |

## 5. Observability, evaluations, and operational scope

- **Run timeline.** The API merges stored stage events with run and approval timestamps. An agent stage shows elapsed time and the outcome of its work. Failed runs expose the recorded failure reason.
- **Usage.** Model responses contribute input, cached input, output and total token counts. Generation, verification, and retries are included when the provider returns usage. A response rejected during schema validation can still count. Estimates use known standard rates for the supported GPT-5 mini model identifiers. Unpriced responses retain their token counts. Estimates are for observed responses rather than an invoice reconciliation.
- **Evaluation.** The 30-scenario runner shares intermediate outputs across cases in an invocation. It evaluates the agents, routing and policy without making commerce writes. An end-to-end approval flow is verified separately with the demo stack.
- **Queue and recovery.** Database row locks protect concurrent job claims, and graph checkpoints support approval resume. A worker crash after a claim can leave a run in `running` because there is no lease-based recovery. Go tool replay protection covers already executed approved mutations.
- **Deployment.** The included Compose file targets a local demo with a single worker service. Public deployment needs authenticated access, protected internal ports, secret management, and a plan for stalled jobs and model budget limits.
