# Services

One service, one directory, one clear ownership boundary — no shared
mutable state between services outside the message queue / DB (see root
`CLAUDE.md`). Each service owns its own Postgres database and its own
Alembic migration history.

- `tenant-service/` — Tenant CRUD, isolation, plan, billing, limits (Phase 1)
- `employee-service/` — Employee CRUD, AD/Google Workspace sync (Phase 1)

Every service that stores tenant-scoped data depends on `libs/tenancy` for
its ORM base and session middleware — see the root [README](../README.md#tenant-isolation).
