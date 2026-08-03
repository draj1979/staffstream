# Services

One service, one directory, one clear ownership boundary — no shared mutable
state between services outside the message queue / DB (see root `CLAUDE.md`).

This directory is currently empty: we are on **Phase 0 (walking skeleton)**.
The first services (Tenant Service, Employee Service) land in Phase 1.

Each service, once added, will be a self-contained FastAPI app with its own
`pyproject.toml`, tests, and Dockerfile, following whatever ORM base /
tenant-isolation middleware is established for the platform.
