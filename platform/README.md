# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 7 — Analytics Service: usage, tokens, cost, conversation count,
agent health, and productivity metrics, exposed via Admin/Finance/IT
dashboards.**

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL (one logical database per service) — Cache: Redis
- Migrations: Alembic — CI: GitHub Actions
- Auth: argon2 password hashing, HS256 JWT access tokens, opaque hashed refresh tokens
- LLM: Anthropic Claude via the official SDK, behind a provider-abstraction interface
- Embeddings: Voyage AI (`voyage-3-lite`, 512-dim) — Vector DB: pgvector
- Containers: one Dockerfile per service — Orchestration: Kubernetes (single namespace)
- Events: RabbitMQ (topic exchange) — LLM usage / chat interaction events, consumed by Analytics Service

## Tenant isolation

Every tenant-scoped table gets its filtering for free from [libs/tenancy](libs/tenancy) —
a shared SQLAlchemy base (`TenantScopedBase`) and a session-level event
listener that injects `WHERE tenant_id = :current_tenant` into every
SELECT/UPDATE/DELETE, and stamps/validates `tenant_id` on INSERT. A
hand-written query against a tenant-scoped table cannot forget the filter —
it isn't optional per-query, it's wired into the ORM session itself. See
[libs/tenancy/src/tenancy/session.py](libs/tenancy/src/tenancy/session.py).

## Auth

[libs/auth](libs/auth) is the shared JWT/password layer every service depends
on. **Auth Service** (`services/auth-service`) is the only service that
issues tokens or touches credentials:

- `POST /auth/signup` — creates the employee (via a service-to-service call
  to Employee Service, see below) and its credential row, returns a token pair
- `POST /auth/login` — verifies the argon2 password hash, returns a token pair
- `POST /auth/refresh` — rotates the refresh token (old one is revoked the
  moment it's used, so a stolen-and-replayed token stops working)
- `POST /auth/logout` — revokes a refresh token

Access tokens are short-lived JWTs (15 min default) carrying `tenant_id` and
`sub` (employee_id) in the claims — see [libs/auth/src/auth/jwt.py](libs/auth/src/auth/jwt.py).
Refresh tokens are opaque random strings; only their SHA-256 hash is stored,
so they can be genuinely revoked (unlike a stateless JWT, which can't be
un-issued before it expires).

Every route in Tenant Service and Employee Service now requires a bearer
JWT via the `require_auth` FastAPI dependency
([libs/auth/src/auth/dependency.py](libs/auth/src/auth/dependency.py)), which
verifies the token and sets the tenant context for the tenancy layer above —
replacing the old `X-Tenant-Id` header trust from Phase 1. Two exceptions,
both deliberate:

- `POST /tenants` (Tenant Service) stays unauthenticated — it's the platform
  onboarding entry point; a brand-new organization has no employee, and
  therefore no token, until its tenant exists.
- `POST /employees` (Employee Service) also accepts a short-lived
  **system-scoped** token, minted only by Auth Service for the one
  service-to-service call during signup (creating the very first employee,
  before anyone has credentials to log in with). Every other route accepts
  `"user"` scope only.
- Auth Service's own `/auth/*` endpoints are pre-JWT by nature (that's what
  they issue) and still use the `X-Tenant-Id` header via `tenancy.tenant_context`.

`GET /tenants` (list all tenants) requires system scope — no employee JWT
should ever list another company's tenant row. `GET`/`PATCH /tenants/{id}`
require a user token whose `tenant_id` claim matches the path.

## Agent Registry

One agent profile per employee, enforced by a `(tenant_id, employee_id)`
unique constraint at the DB level — `services/agent-registry`. Fields: name,
personality, model, temperature, prompt, memory_namespace, knowledge_sources,
skills, permissions. `memory_namespace` defaults to `"{tenant_id}:{employee_id}"`
if not supplied, ready for Phase 4's Memory Service to key off of.

Employee Service auto-creates a default agent right after an employee is
created — same service-to-service bootstrap pattern as auth-service creating
the employee itself (a short-lived system-scoped token, since the new
employee has no session of its own yet), and writes the resulting `agent_id`
back onto the `Employee` row. Like the auth-service → employee-service call,
this is a synchronous multi-service write with no saga/outbox — a failure
here surfaces as a 502 rather than silently losing the agent; a real fix
needs the message queue mentioned in the tech stack but not built yet.

## LLM Gateway

`services/llm-gateway` is a thin, authenticated `POST /generate` in front of
an internal `Provider` interface
([provider.py](services/llm-gateway/src/llm_gateway/provider.py)) and an
`LLMGateway` registry that dispatches by provider name. Only `"claude"` is
registered (via the official Anthropic SDK) — Phase 10 registers GPT,
Gemini, etc. as more `Provider` implementations, with no changes needed to
the gateway or its callers.

## OpenClaw Runtime

`services/openclaw-runtime` implements the request flow from CLAUDE.md:
`POST /chat` authenticates the caller (`require_auth`, which also identifies
tenant and employee from the JWT), fetches that employee's agent from Agent
Registry, and calls LLM Gateway with the agent's model/prompt/temperature to
produce a reply.

It's deliberately stateless — the whole point of "OpenClaw itself is
stateless" from CLAUDE.md. Every `/chat` call re-fetches the agent and its
memory from their owning services over HTTP; nothing is cached in the
process between requests, so changing an agent's model, prompt, or memory
takes effect on the very next message with no restart or cache
invalidation anywhere (see
[runtime.py](services/openclaw-runtime/src/openclaw_runtime/runtime.py) and
its no-caching test). It forwards the caller's own bearer token to Agent
Registry, Memory Service, and LLM Gateway rather than minting a new one —
the caller already has a valid session, so there's no separate identity to
establish.
[knowledge.py](services/openclaw-runtime/src/openclaw_runtime/knowledge.py)
is still a no-op stub with the real service's eventual signature — Phase 5
replaces its body, not its callers.

## Memory Service

`services/memory-service` — Postgres only, vector DB deferred — stores four
kinds of per-employee memory, all scoped by `(tenant_id, memory_namespace)`:
conversation history (append-only, chronological), long-term memory notes,
preferences (key/value, upserted), and learned facts. `memory_namespace` is
the same value as the owning Agent's `memory_namespace` from Phase 3 — it's
the partition key the API is organized around (`/memory/{memory_namespace}/...`).
`tenant_id` still goes through the standard tenancy filter on every query
regardless of what the namespace string happens to be, so even a namespace
collision across tenants can't leak data (there's a test for exactly this).

OpenClaw's Load Memory step ([memory.py](services/openclaw-runtime/src/openclaw_runtime/memory.py))
fetches all four kinds before calling the LLM: conversation history feeds
the messages list, and long-term/preferences/facts get folded into the
system prompt alongside personality. Store Memory happens only after a
successful LLM reply — it appends the user message and assistant reply as
two new conversation turns; a failed LLM call (e.g. no `ANTHROPIC_API_KEY`)
correctly stores nothing.

## Knowledge Platform

`services/knowledge-service` handles the three knowledge scopes from the
HLD: **company** (tenant-wide), **department** (a department name string —
Employee Service has no separate Department entity, so this keys off
`Employee.department` directly), and **personal** (a single employee;
always forced to the uploader's own `employee_id`, never settable to
someone else's). Only PDF and DOCX for now.

Pipeline (`POST /documents`, synchronous — no queue yet): extract text
(`pypdf` / `python-docx`) → chunk (fixed-size sliding window with overlap,
snapped to whitespace) → embed each chunk (Voyage AI) → store in pgvector,
every row carrying `tenant_id` (through the standard tenancy filter, same
as every other table) plus `scope`/`department`/`employee_id` denormalized
from the parent document for fast filtering. A failed step marks the
document `status: "failed"` with the real error message rather than
leaving it stuck.

`POST /search` embeds the query (Voyage, `input_type="query"` — chunks are
embedded with `input_type="document"`; Voyage's models are tuned to expect
that distinction) and ranks chunks by pgvector cosine distance, filtered to
whatever scopes the caller passes: always company-wide, plus their
department and/or employee_id if supplied. There's a test proving
`tenant_id` remains the real isolation boundary even if two tenants
happened to pick an identical `department` string.

pgvector's similarity search is real Postgres SQL (the `<=>` operator) —
there's no meaningful SQLite fallback for it, unlike every other service's
tests. `services/knowledge-service`'s tests connect to a real
Postgres+pgvector instance and **skip cleanly** (not fail) if one isn't
reachable; `docker compose up -d postgres-vector` provides one locally
(see below), and CI runs a dedicated job against a real
`pgvector/pgvector:pg16` container. The embedding calls themselves are
always mocked in tests — Voyage is a real paid API, and nothing needed to
call it for real to prove the pgvector math works.

OpenClaw's Load Knowledge step
([knowledge.py](services/openclaw-runtime/src/openclaw_runtime/knowledge.py))
fetches the employee's department from Employee Service (one more
always-fresh HTTP call, no caching, same as everything else in OpenClaw),
searches personal + that department + company-wide using the chat message
itself as the query, and folds any results into the system prompt
alongside memory.

## API Gateway

`services/api-gateway` is the one front door — every other service's
Service should stay ClusterIP-only in a real deployment; this is the only
one meant to be reachable from outside the cluster (see its k8s manifest).
It reverse-proxies by path prefix (`/tenants` -> Tenant Service, `/chat` ->
OpenClaw Runtime, etc. — see
[routing.py](services/api-gateway/src/api_gateway/routing.py)) and adds
three things no individual backend service has on its own:

- **Per-tenant rate limiting** — a Redis-backed fixed-window counter
  ([rate_limit.py](services/api-gateway/src/api_gateway/rate_limit.py)),
  keyed by the `tenant_id` claim from the caller's JWT (verified, so a
  client can't dodge its own limit by forging the claim), falling back to
  the `X-Tenant-Id` header or the client IP for pre-auth routes like
  signup. One tenant maxing out its quota never touches anyone else's
  bucket. This is deliberately *not* an authorization check — the gateway
  never rejects a request for a missing/invalid/expired token; that's
  still each backend's own `require_auth`, exactly as before.
- **Request size limits** — a fast `Content-Length` pre-check plus a real
  streaming byte-count guard (so a lying header can't bypass it), with a
  much higher ceiling for knowledge-service's upload path than everywhere
  else.
- **Centralized error sanitization** — any 5xx from a backend (or a
  proxying failure like a timeout) gets its body replaced with a generic
  `{"detail": "..."}` message before it ever reaches the client; whatever
  the backend actually said — stack trace, DB error text, anything — is
  logged server-side and never forwarded. 4xx responses pass through
  unchanged, since those are messages the backend already wrote to be
  client-safe.

## Analytics Service

`services/analytics-service` never sits on the `/chat` request path — it's
fed asynchronously so LLM Gateway/OpenClaw latency is never coupled to
analytics ingestion. [libs/events](libs/events) defines the shared event
schemas and a thin `aio-pika`-based pub/sub wrapper over a RabbitMQ topic
exchange (`staffstream.events`):

- **LLM Gateway** publishes an `LLMUsageEvent` (tenant, employee, agent,
  provider, model, input/output tokens, `cost_usd` from
  [pricing.py](services/llm-gateway/src/llm_gateway/pricing.py)) after
  every successful `/generate` call.
- **OpenClaw Runtime** publishes a `ChatInteractionEvent` (tenant,
  employee, agent, success/failure, which stage failed if any, latency)
  after every `/chat` call, success or failure — agent attribution
  survives even a downstream failure via a small `TurnContext` object
  threaded through the call.

Both publish sites use `asyncio.create_task` (never awaited by the route
handler) with a strong reference kept in `app.state.background_tasks`, and
swallow their own publish failures internally — a RabbitMQ outage degrades
analytics, never the chat/generate response. Analytics Service's own
consumers ([consumer.py](services/analytics-service/src/analytics_service/consumer.py))
reconnect with exponential backoff and set the tenant context straight
from the event payload (there's no JWT on a queue message) before writing
a row; a message that fails to parse is logged and dropped rather than
redelivered forever (documented as a known simplification — no
dead-letter queue yet).

Three read endpoints aggregate at query time (`crud.py`) per the HLD's
dashboard split — `GET /analytics/admin` (conversation count, success
rate, active employees/agents, token/cost totals), `/analytics/finance`
(cost by model, by employee, daily trend), and `/analytics/it` (error
rate, avg/p95 latency, per-agent health, errors by failure stage) — all
behind `require_auth()` and tenant-scoped through the same tenancy layer
as everything else, with `from_date`/`to_date` query params defaulting to
a trailing 30-day window. Role-gating which dashboard an employee can see
is RBAC, deferred to Phase 9 like everywhere else in the platform.
`SkillUsageEventRow`/`SkillUsageEvent` exist end-to-end in the schema
already, ready for Phase 8's Skill Marketplace to start publishing into —
no producer emits them yet.

## Containers & Kubernetes

Every service has its own `Dockerfile` (multi-stage, `uv`-based, built
from the repo root since this is a uv workspace — see any service's
Dockerfile for the exact command). `make docker-build` builds all ten.
`infra/k8s/` has Deployment + Service manifests for all ten plus the
namespace, ConfigMap, Secret template, and in-cluster Postgres/Redis/RabbitMQ —
see [infra/k8s/README.md](infra/k8s/README.md) for the full deploy flow.
Every Deployment's `livenessProbe` hits `/healthz` (process alive — never
checks dependencies, so a DB blip doesn't get the pod restarted) and its
`readinessProbe` hits `/readyz` (DB-backed services actually check DB
connectivity; stateless ones just confirm the process is up) — so k8s
stops routing traffic to a pod that can't actually serve, without
restarting a pod that just needs its dependency to come back.

## Local development

```bash
cp .env.example .env
make up       # start Postgres + Redis + Postgres/pgvector + RabbitMQ via docker-compose
make migrate  # run Alembic migrations for every service with a database
make lint     # ruff
make test     # pytest (fast, sqlite-backed where possible; Knowledge Service
              # skips cleanly without a live Postgres+pgvector, libs/events
              # skips cleanly without a live RabbitMQ; nothing ever calls the
              # real Anthropic or Voyage AI APIs)
make run-tenant-service     # http://localhost:8001
make run-employee-service   # http://localhost:8002
make run-auth-service       # http://localhost:8003
make run-agent-registry     # http://localhost:8004
make run-llm-gateway        # http://localhost:8005
make run-openclaw-runtime   # http://localhost:8006
make run-memory-service     # http://localhost:8007
make run-knowledge-service  # http://localhost:8008
make run-api-gateway        # http://localhost:8000
make run-analytics-service  # http://localhost:8009
make down     # stop containers

make docker-build   # build all 10 service images (staffstream/<service>:latest)
```

To try the whole platform containerized rather than via `make run-*`, see
[infra/k8s/README.md](infra/k8s/README.md) — or run individual images
directly with `docker run` (each `Dockerfile`'s header comment has the
exact build command).

Postgres is exposed on host port **5433** (not 5432) to avoid clashing with
any other local Postgres instance; Knowledge Service's separate
Postgres+pgvector instance is on **5434** (a dedicated container, not a
retrofit of the shared one — see `docker-compose.yml`'s `postgres-vector`
service). `JWT_SECRET_KEY` must be identical across every service — see
`.env.example`. `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` are only needed to
actually call Claude / Voyage; without them the services still start and
route correctly, calls just fail with a normal auth error from the
provider.

## Layout

```
libs/
  tenancy/            shared tenant-isolation ORM base + session middleware
  auth/                shared JWT issuance/verification + password hashing
  events/              shared event schemas + RabbitMQ pub/sub (publisher, consumer)
services/
  tenant-service/      Tenant CRUD: plan, storage quota, LLM config, branding, subscription
  employee-service/    Employee CRUD: department, designation, manager, roles, agent_id
  auth-service/        Signup, login, refresh, logout — the only service touching credentials
  agent-registry/      One agent profile per employee: model, prompt, temperature, memory namespace, ...
  llm-gateway/          Provider abstraction over LLMs; Claude only for now — emits LLM usage events
  openclaw-runtime/     Stateless: POST /chat — loads agent + memory + knowledge, calls LLM Gateway, stores the turn, emits chat interaction events
  memory-service/       Per-employee memory: conversation, long-term, preferences, learned facts
  knowledge-service/    Company/department/personal knowledge: PDF/DOCX -> chunks -> pgvector
  api-gateway/          Front door: per-tenant rate limiting, size limits, sanitized errors, reverse proxy
  analytics-service/    Usage/tokens/cost/health from queued events — Admin/Finance/IT dashboards
tests/                 root-level smoke tests
docs/                  architecture and design docs
infra/
  docker/               docker-compose init scripts
  k8s/                  Deployment/Service/ConfigMap/Secret manifests, single namespace
```

Every service directory also has its own `Dockerfile`.
