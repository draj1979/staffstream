# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 3 — Agent Registry + LLM Gateway (Claude only for now).** (OpenClaw
runtime wiring and multi-provider support are separate, later work.)

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL (one logical database per service) — Cache: Redis
- Migrations: Alembic — CI: GitHub Actions
- Auth: argon2 password hashing, HS256 JWT access tokens, opaque hashed refresh tokens
- LLM: Anthropic Claude via the official SDK, behind a provider-abstraction interface

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

## Local development

```bash
cp .env.example .env
make up       # start Postgres + Redis via docker-compose
make migrate  # run Alembic migrations for every service with a database
make lint     # ruff
make test     # pytest (fast, sqlite-backed; LLM Gateway tests never call the real Anthropic API)
make run-tenant-service     # http://localhost:8001
make run-employee-service   # http://localhost:8002
make run-auth-service       # http://localhost:8003
make run-agent-registry     # http://localhost:8004
make run-llm-gateway        # http://localhost:8005
make down     # stop containers
```

Postgres is exposed on host port **5433** (not 5432) to avoid clashing with
any other local Postgres instance. `JWT_SECRET_KEY` must be identical across
every service — see `.env.example`. `ANTHROPIC_API_KEY` is only needed to
actually call Claude; without it the gateway still starts and routes
correctly, calls just fail with a normal 401 from Anthropic.

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
tests/                 root-level smoke tests
docs/                  architecture and design docs
infra/                 docker-compose init scripts, deployment infra
```
