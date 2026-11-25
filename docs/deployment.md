# CommercePilot on a Compute Engine VM

Use a dedicated demo database containing only synthetic data. This deployment
runs two web entry points on one VM and shares run history through PostgreSQL.

| Entry point | Access | Operations |
| --- | --- | --- |
| Public demo | HTTPS through Caddy | Browse product signals and saved run history |
| Operator dashboard | SSH tunnel to VM loopback port 5173 | Start runs, change simulated prices, and submit approvals |

PostgreSQL, Go MCP, and both FastAPI services use the Compose network without
published host ports. The public API blocks writes and opens database sessions
in read-only mode by default. The operator dashboard and demo preview bind to
the VM loopback interface. Caddy
proxies exclusively to the public demo. The OpenAI key is used by the Python
worker for live processing. The public API is deployed without that key.

## Start privately

1. On a Compute Engine VM with Docker Engine and
   [Docker Compose 2.24.4 or later](https://docs.docker.com/reference/compose-file/merge/#replace-value),
   clone the repository.
2. Copy `.env.example` to `.env`. Set `POSTGRES_PASSWORD` to a strong URL-safe
   password before the database volume is first initialized. Set the OpenAI key
   and model for the operator workflow. Keep the file private.
3. Start the stack and seed the demo data on the VM.

```bash
docker compose -f compose.yaml -f compose.gcp.yaml up -d --build --wait
docker compose -f compose.yaml -f compose.gcp.yaml exec -T api python scripts/seed_catalog.py
docker compose -f compose.yaml -f compose.gcp.yaml exec -T api python scripts/seed_reviews.py
```

Forward both dashboards to your computer over SSH. If your VM is configured
for [SSH through Google Cloud IAP](https://docs.cloud.google.com/compute/docs/connect/ssh-using-iap),
run this from your computer:

```bash
gcloud compute ssh VM_NAME --zone ZONE --tunnel-through-iap -- \
  -N -L 127.0.0.1:15173:127.0.0.1:5173 -L 127.0.0.1:18088:127.0.0.1:8088
```

Open the [operator dashboard](http://localhost:15173) and the
[demo preview](http://localhost:18088). Run a cycle in the operator dashboard
and approve its drafts as needed. Refresh the preview to see the shared history.

## Publish the demo

1. Point a hostname you control to the VM's external address and set
   `COMMERCEPILOT_PUBLIC_HOST` to that hostname in `.env`.
2. Permit inbound TCP 80 and 443 for that VM in the GCP firewall. Keep database,
   MCP, API, and dashboard ports private. Configure SSH access separately.
3. Enable the HTTPS edge.

```bash
docker compose -f compose.yaml -f compose.gcp.yaml --profile public-tls up -d --wait
```

Check that the HTTPS page loads and that the public endpoint reports
`"read_only_demo": true` at `/api/capabilities`. Verify that the operator
endpoint reports `false`, and that a public POST to `/api/runs` returns 403.
Use a dedicated demo dataset and avoid entering personal details in approvals.
Before trial credits expire, back up PostgreSQL and decide whether to keep the VM.
