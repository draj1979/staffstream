# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 2 — Basic auth: email/password + JWT.** (SSO/OAuth/MFA deferred to Phase 9.)

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL (one logical database per service) — Cache: Redis
- Migrations: Alembic — CI: GitHub Actions
- Auth: argon2 password hashing, HS256 JWT access tokens, opaque hashed refresh tokens

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

## Local development

```bash
cp .env.example .env
make up       # start Postgres + Redis via docker-compose
make migrate  # run Alembic migrations for all three services
make lint     # ruff
make test     # pytest (fast, sqlite-backed)
make run-tenant-service     # http://localhost:8001
make run-employee-service   # http://localhost:8002
make run-auth-service       # http://localhost:8003
make down     # stop containers
```

Postgres is exposed on host port **5433** (not 5432) to avoid clashing with
any other local Postgres instance. `JWT_SECRET_KEY` must be identical across
every service — see `.env.example`.

## Layout

```
libs/
  tenancy/            shared tenant-isolation ORM base + session middleware
  auth/                shared JWT issuance/verification + password hashing
services/
  tenant-service/      Tenant CRUD: plan, storage quota, LLM config, branding, subscription
  employee-service/    Employee CRUD: department, designation, manager, roles, agent_id
  auth-service/        Signup, login, refresh, logout — the only service touching credentials
tests/                 root-level smoke tests
docs/                  architecture and design docs
infra/                 docker-compose init scripts, deployment infra
```
