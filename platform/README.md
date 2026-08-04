# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 1 — Tenant Service + Employee Service, tenant_id isolation pattern.**

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL (one logical database per service) — Cache: Redis
- Migrations: Alembic — CI: GitHub Actions

## Tenant isolation

Every tenant-scoped table gets its filtering for free from [libs/tenancy](libs/tenancy) —
a shared SQLAlchemy base (`TenantScopedBase`) and a session-level event
listener that injects `WHERE tenant_id = :current_tenant` into every
SELECT/UPDATE/DELETE, and stamps/validates `tenant_id` on INSERT. A
hand-written query against a tenant-scoped table cannot forget the filter —
it isn't optional per-query, it's wired into the ORM session itself. See
[libs/tenancy/src/tenancy/session.py](libs/tenancy/src/tenancy/session.py).

The current tenant comes from the `X-Tenant-Id` request header via the
`tenant_context` FastAPI dependency (temporary bridge — Phase 2 swaps this
for the tenant_id embedded in the authenticated JWT, same dependency shape).

## Local development

```bash
cp .env.example .env
make up       # start Postgres + Redis via docker-compose
make migrate  # run Alembic migrations for both services
make lint     # ruff
make test     # pytest (fast, sqlite-backed)
make run-tenant-service     # http://localhost:8001
make run-employee-service   # http://localhost:8002
make down     # stop containers
```

Postgres is exposed on host port **5433** (not 5432) to avoid clashing with
any other local Postgres instance.

## Layout

```
libs/
  tenancy/            shared tenant-isolation ORM base + session middleware
services/
  tenant-service/      Tenant CRUD: plan, storage quota, LLM config, branding, subscription
  employee-service/    Employee CRUD: department, designation, manager, roles, agent_id
tests/                 root-level smoke tests
docs/                  architecture and design docs
infra/                 docker-compose init scripts, deployment infra
```
