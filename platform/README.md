# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 5 — Knowledge Platform: PDF/DOCX upload with pgvector retrieval.**
(Other knowledge sources — SharePoint, Drive, Confluence, Notion, web, DB —
are future work; only PDF/DOCX for now.)

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL (one logical database per service) — Cache: Redis
- Migrations: Alembic — CI: GitHub Actions
- Auth: argon2 password hashing, HS256 JWT access tokens, opaque hashed refresh tokens
- LLM: Anthropic Claude via the official SDK, behind a provider-abstraction interface
- Embeddings: Voyage AI (`voyage-3-lite`, 512-dim) — Vector DB: pgvector

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

## Local development

```bash
cp .env.example .env
make up       # start Postgres + Redis + Postgres/pgvector via docker-compose
make migrate  # run Alembic migrations for every service with a database
make lint     # ruff
make test     # pytest (fast, sqlite-backed where possible; Knowledge Service
              # skips cleanly without a live Postgres+pgvector; nothing ever
              # calls the real Anthropic or Voyage AI APIs)
make run-tenant-service     # http://localhost:8001
make run-employee-service   # http://localhost:8002
make run-auth-service       # http://localhost:8003
make run-agent-registry     # http://localhost:8004
make run-llm-gateway        # http://localhost:8005
make run-openclaw-runtime   # http://localhost:8006
make run-memory-service     # http://localhost:8007
make run-knowledge-service  # http://localhost:8008
make down     # stop containers
```

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
services/
  tenant-service/      Tenant CRUD: plan, storage quota, LLM config, branding, subscription
  employee-service/    Employee CRUD: department, designation, manager, roles, agent_id
  auth-service/        Signup, login, refresh, logout — the only service touching credentials
  agent-registry/      One agent profile per employee: model, prompt, temperature, memory namespace, ...
  llm-gateway/          Provider abstraction over LLMs; Claude only for now
  openclaw-runtime/     Stateless: POST /chat — loads agent + memory + knowledge, calls LLM Gateway, stores the turn
  memory-service/       Per-employee memory: conversation, long-term, preferences, learned facts
  knowledge-service/    Company/department/personal knowledge: PDF/DOCX -> chunks -> pgvector
tests/                 root-level smoke tests
docs/                  architecture and design docs
infra/                 docker-compose init scripts, deployment infra
```
