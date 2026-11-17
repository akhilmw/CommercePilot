# Architecture notes

## Service boundaries

### React application

Presents store data, agent findings, proposals, approval controls, and audit history.
It communicates with FastAPI through REST.

### Python API and LangGraph workflow

Owns agent orchestration, structured handoffs, validation flow, approval pauses,
and workflow persistence. It accesses commerce capabilities through an MCP client.

### Go MCP server

Owns the agent-facing tool contracts. It validates every tool request and will
enforce approval, content-hash, authorization, and idempotency checks for mutations.

### PostgreSQL

Stores products, reviews, competitor snapshots, workflows, agent runs, proposals,
approvals, campaigns, and audit events.

## Initial workflow

```text
Review Agent -----------\
                         -> Orchestrator -> Catalog Agent -> Validation --\
Competitor Agent -------/                     |                         |
                                              -> Campaign Agent --------+-> Human approval
                                                                             |
                                                                             -> Go MCP publish tools
```

No agent may publish directly. Agents create proposals; deterministic validation
and a human approval decision must precede every mutation.

