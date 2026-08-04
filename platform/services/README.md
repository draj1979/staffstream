# Services

One service, one directory, one clear ownership boundary — no shared
mutable state between services outside the message queue / DB (see root
`CLAUDE.md`). Each service owns its own Postgres database and its own
Alembic migration history.

- `tenant-service/` — Tenant CRUD, isolation, plan, billing, limits (Phase 1)
- `employee-service/` — Employee CRUD, AD/Google Workspace sync (Phase 1)
- `auth-service/` — Login, registration, JWT issuance/revocation (Phase 2; SSO/OAuth/MFA deferred to Phase 9)
- `agent-registry/` — One agent profile per employee (Phase 3)
- `llm-gateway/` — Provider abstraction over LLMs, Claude only for now (Phase 3; multi-provider is Phase 10)
- `openclaw-runtime/` — Stateless agent execution: `POST /chat` (Phase 3; no database — nothing is cached in-process, everything is re-fetched from Agent Registry / Memory Service / Knowledge Service / LLM Gateway on every call)
- `memory-service/` — Per-employee memory: conversation, long-term, preferences, learned facts/behaviour (Phase 4; Postgres only, vector DB deferred)
- `knowledge-service/` — Company/department/personal knowledge: PDF/DOCX upload, chunking, Voyage AI embeddings, pgvector retrieval (Phase 5; its own dedicated Postgres+pgvector instance, not the shared one the other services use)
- `api-gateway/` — Front door: per-tenant rate limiting, request size limits, centralized error sanitization, reverse proxy to every other service (Phase 6; no database — Redis-backed rate limiting only)

Every service now has its own `Dockerfile` and a matching Deployment +
Service in `infra/k8s/services/` (Phase 6) — see the root
[README's Containers & Kubernetes section](../README.md#containers--kubernetes)
and [infra/k8s/README.md](../infra/k8s/README.md).

Every service that stores tenant-scoped data depends on `libs/tenancy` for
its ORM base and session middleware, and every service that verifies or
issues tokens depends on `libs/auth` — see the root
[README](../README.md#tenant-isolation) and its [Auth section](../README.md#auth).
