# Two-VM GCP demo deployment

A simpler, cheaper alternative to [`../terraform/gcp`](../terraform/gcp)'s
GKE Autopilot + Cloud SQL + Memorystore + Workload Identity setup — two
VMs and `docker compose` instead of a managed cluster and managed
databases. Good for a live demo or cost-conscious proof of concept; **not**
what you'd run in production (no HPA, no per-service least-privilege IAM,
no managed backups, a real SSH surface even if IAP-gated, secrets in a
plaintext `.env` file on disk). See
[`../../docs/gcp-deployment.md`](../../docs/gcp-deployment.md) for the
production path.

## Architecture

```
                 Internet
                     │
                     │ 80/443
                     ▼
   ┌─────────────────────────────────────┐
   │  backend-vm  (static external IP)     │
   │                                        │
   │  Caddy (auto TLS) ──▶ api-gateway      │
   │                          │              │
   │        ┌─────────────────┼──────────┐  │
   │        ▼                 ▼          ▼  │
   │  tenant/employee/auth  llm-gateway  ... │
   │  agent-registry/memory/knowledge        │
   │  openclaw-runtime/analytics-service     │
   └───────────────────┬────────────────────┘
                        │ 5432 / 6379 only
                        │ (firewall-scoped, no other ports)
                        ▼
   ┌─────────────────────────────────────┐
   │  db-vm  (no external IP)             │
   │                                       │
   │  Postgres (pgvector)  +  Redis        │
   │  data on a separate attached disk     │
   │  (/mnt/db-data), not the boot disk    │
   └───────────────────────────────────────┘
```

**11 of the platform's 12 services** run here — only Skill Marketplace is
excluded (see [`backend-compose.yml`](backend-compose.yml)'s top comment
for exactly why: it needs OAuth apps registered per connector to demo
anything). Audit Service and Analytics both run and their read APIs work
against real data, but their event *ingestion* needs a message broker
this two-VM layout doesn't provision — db-vm is Postgres + Redis only,
per the ask. Nothing crashes for lack of one; ingestion and audit logging
just never receive anything, so both will show real-but-empty results
until something adds RabbitMQ. See that file's comment for the specific
code paths that make this a graceful no-op rather than a startup
failure. Analytics and Audit are reached directly by the frontend
(`/analytics/*`, `/audit-logs`) rather than through `api-gateway` — its
`ROUTES` table (`services/api-gateway/src/api_gateway/routing.py`) has no
entries for either service, so Caddy proxies those two path prefixes
straight to their containers instead (see `../Caddyfile`).

## Files

| File | Purpose |
|---|---|
| `db-compose.yml` | Postgres (pgvector) + Redis, data on `/mnt/db-data` |
| `init-db.sh` | Creates the 7 per-service databases + enables pgvector, once, on first Postgres boot |
| `backend-compose.yml` | The 10 app services + Caddy, with per-service DB migration one-shots and health-gated startup ordering |
| `Caddyfile` | Automatic Let's Encrypt TLS, reverse-proxies everything to `api-gateway` |
| `scripts/wait-for.sh` | TCP-reachability wait with exponential backoff (1s→2s→4s…capped at 15s) — bind-mounted into every DB/Redis-backed service so a `db-vm` restart doesn't crash-loop `backend-vm`'s containers |
| `scripts/db-vm-startup.sh` / `scripts/backend-vm-startup.sh` | GCE startup-scripts: install Docker (idempotent), format+mount the data disk (db-vm only, first-boot-only), install and enable the systemd unit |
| `systemd/*.service` | Standalone copies of the units the startup-scripts install, for reference/manual reinstall |
| `setup.sh` | All the `gcloud` provisioning — network, firewall, disk, both VMs |
| `db.env.example` / `backend.env.example` | What to copy to `.env` on each VM |

## One-time setup

```bash
cd infra/gcp-vm-demo
PROJECT_ID=your-project-id REGION=asia-south1 ./setup.sh
```

Creates (all idempotent — safe to re-run):
- A dedicated custom-mode VPC + subnet (not the default network)
- A Cloud Router + Cloud NAT — `db-vm` has no external IP, so this is its
  only route to the internet (needed once, for its startup-script's
  Docker install and the Postgres/Redis image pulls)
- Firewall rules: **public 80/443 → `backend-vm` only**; **`backend-vm` → `db-vm` on 5432/6379 only** (scoped by network tag, not IP range); **SSH only via IAP's fixed range `35.235.240.0/20`** — no open SSH to the internet, ever
- A dedicated GSA for `backend-vm` with `roles/artifactregistry.reader` only (pulls images via the VM's attached identity + `docker-credential-gcr`, no key file, no broader permissions)
- `db-vm`'s separate data disk (`pd-balanced`, 50GB default) — attached but not yet formatted (the startup-script formats it on first boot only, never on a disk that already has a filesystem)
- Both VMs, each with its startup-script wired in via instance metadata

The script prints `db-vm`'s internal IP and `backend-vm`'s static
external IP at the end — you need both for the next steps.

## Bring the stack up

1. **DNS**: point `DEMO_DOMAIN`'s A record at the static external IP `setup.sh` printed. Caddy's ACME HTTP-01 challenge fails until this resolves.

2. **Fill in real config** (never commit these — both are gitignored):
   ```bash
   cp db.env.example db.env           # POSTGRES_PASSWORD
   cp backend.env.example backend.env # JWT_SECRET_KEY, DB_VM_INTERNAL_IP, DEMO_DOMAIN, API keys, same POSTGRES_PASSWORD as db.env
   ```

3. **Copy to each VM** (over SSH via IAP — this is deliberately a separate step from VM creation, not baked into the startup-script metadata, since instance metadata is visible to anyone with `compute.instances.get` and is not where real secrets belong):
   ```bash
   gcloud compute scp --zone=asia-south1-b --tunnel-through-iap \
     db-compose.yml init-db.sh db.env db-vm:/opt/staffstream/

   gcloud compute scp --zone=asia-south1-b --tunnel-through-iap --recurse \
     backend-compose.yml Caddyfile scripts backend.env backend-vm:/opt/staffstream/
   ```

4. **First bring-up** (systemd is already installed and enabled by the startup-scripts; this just renames `.env` into place and gives it its first kick — every reboot after this is automatic, no SSH needed):
   ```bash
   gcloud compute ssh db-vm --zone=asia-south1-b --tunnel-through-iap -- \
     'cd /opt/staffstream && mv db.env .env && sudo systemctl restart staffstream-db.service'

   gcloud compute ssh backend-vm --zone=asia-south1-b --tunnel-through-iap -- \
     'cd /opt/staffstream && mv backend.env .env && sudo systemctl restart staffstream-backend.service'
   ```

5. **Verify**:
   ```bash
   curl https://your-demo-domain/healthz   # api-gateway, proxied through Caddy
   gcloud compute ssh backend-vm --zone=asia-south1-b --tunnel-through-iap -- \
     'cd /opt/staffstream && docker compose -f backend-compose.yml ps'
   ```

## CI/CD

[`.github/workflows/deploy-gcp.yml`](../../.github/workflows/deploy-gcp.yml)
builds and pushes all 13 images (12 backend services + `web`) on every
push to `main`, tagged with the commit SHA, using Workload Identity
Federation (no service account key file). It then SSHes into
`backend-vm` over IAP — the same no-public-SSH path `setup.sh` sets up —
to bump `IMAGE_TAG` in `.env`, `docker compose pull && up -d`, and wait
for every container to report healthy. A smoke test against the live
public domain (`GET /healthz`, then a real authenticated `POST /chat`)
gates success; either the deploy or the smoke test failing rolls
`backend-vm` back to whatever `IMAGE_TAG` was running before that run
started, via `scripts/ci-rollback.sh`.

One-time setup beyond what `setup.sh` already does:
- `setup.sh` itself grants the CI deployer service account
  (`github-actions-deployer@<project>.iam.gserviceaccount.com` by
  default — override with `CI_DEPLOYER_SA_EMAIL`) `roles/iap.tunnelResourceAccessor`
  and an instance-scoped `roles/compute.osAdminLogin` on `backend-vm`,
  and enables OS Login on the VM — all idempotent, safe on a re-run.
- Repo variables (Settings → Secrets and variables → Actions →
  Variables): `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`,
  `GCP_DEPLOYER_SA_EMAIL`, `BACKEND_VM_NAME`, `BACKEND_VM_ZONE`, `DEMO_DOMAIN`.
- Repo secrets: `SMOKE_TEST_TENANT_ID`, `SMOKE_TEST_EMAIL`,
  `SMOKE_TEST_PASSWORD` — a real tenant + employee login the smoke test
  uses for its `/chat` call. A demo-only account is fine; it never needs
  more than a normal employee's own access.

## What makes this resilient to a `db-vm` restart

This was an explicit requirement, not an afterthought — a few things
work together:

1. **`scripts/wait-for.sh`** — every DB/Redis-backed container's
   `entrypoint` waits for TCP reachability (exponential backoff, capped
   at 15s between attempts) before ever invoking `alembic` or `uvicorn`.
   A `db-vm` reboot mid-session means `backend-vm`'s containers sit
   waiting and retrying, not crash-looping.
2. **The application layer was already lazy** — none of these services'
   `Dockerfile`s run migrations as part of the container's own `CMD`
   (that's what the separate `migrate-*` one-shot containers are for),
   and `libs/tenancy`'s `make_engine()` / `redis.asyncio.from_url()` both
   connect lazily with `pool_pre_ping=True`, not eagerly at process
   startup. A request that hits the DB mid-outage gets a normal 500, not
   a crashed process — verified by reading the actual `db.py`/`main.py`
   pattern used across every service before adding `wait-for.sh` on top,
   not assumed.
3. **`restart: unless-stopped`** on every container — covers a container
   that dies for an unrelated reason without a full VM reboot.
4. **The systemd units** — cover a full VM reboot; `docker compose up -d`
   runs automatically on boot via `staffstream-db.service` /
   `staffstream-backend.service`, no manual SSH session required.

## Cost note

Two small-to-medium VMs plus a modest data disk — meaningfully cheaper
than the GKE path's managed Cloud SQL + Memorystore + Autopilot cluster
fee, at the cost of everything GCP manages for you there (backups,
failover, patching, IAM-scoped-per-service secrets). Right tool for a
demo; not a recommendation for anything handling real tenant data long-term.
