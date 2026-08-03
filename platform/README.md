# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 0 — walking skeleton.** Monorepo scaffold, CI, local docker-compose
(Postgres, Redis). No services yet — those start in Phase 1.

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL — Cache: Redis
- CI: GitHub Actions

## Local development

```bash
cp .env.example .env
make up      # start Postgres + Redis via docker-compose
make lint    # ruff
make test    # pytest
make down    # stop containers
```

## Layout

```
services/   one directory per service (empty until Phase 1)
tests/      root-level smoke tests
docs/       architecture and design docs
infra/      docker-compose, deployment infra
```
