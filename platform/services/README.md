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
- `openclaw-runtime/` — Stateless agent execution: `POST /chat` (Phase 3; no database — nothing is cached in-process, everything is re-fetched from Agent Registry / Memory Service / LLM Gateway on every call)
- `memory-service/` — Per-employee memory: conversation, long-term, preferences, learned facts/behaviour (Phase 4; Postgres only, vector DB deferred)

Every service that stores tenant-scoped data depends on `libs/tenancy` for
its ORM base and session middleware, and every service that verifies or
issues tokens depends on `libs/auth` — see the root
[README](../README.md#tenant-isolation) and its [Auth section](../README.md#auth).
