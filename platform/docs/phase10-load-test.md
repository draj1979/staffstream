# Phase 10 multi-tenant load test

Ran [`scripts/load_test.py`](../scripts/load_test.py) against the real local
stack (Postgres, Redis, RabbitMQ via `docker compose up -d`, plus
tenant-service, employee-service, auth-service, agent-registry, and
api-gateway run directly with `uvicorn`) — not mocks. The script drives all
traffic through the API Gateway, the same path real requests take.

## What it checks

1. **Tenant isolation under concurrency.** Provisions N tenants (each with
   one admin employee) concurrently, then has every tenant list `GET
   /employees` concurrently and asserts each one sees *exactly* its own
   employee and nobody else's. This exercises `libs/tenancy`'s
   `with_loader_criteria` injection under real concurrent DB access across
   many tenants at once, not one request at a time the way the unit tests do.
2. **Per-tenant rate limiting under load.** Fires a burst of concurrent
   requests as one tenant, past the gateway's default budget (120
   requests/60s), and confirms some get `429`'d back — while a second,
   otherwise-idle tenant's own request in the same window sails through
   untouched. Proves the Redis bucket key (`tenant:{tenant_id}`) is actually
   per-tenant, not a shared/global counter.

## Results (60 tenants, concurrency=30, rate-limit burst=200)

```
=== Provisioning 60 tenants (concurrency=30) ===
  provisioned 60/60 tenants in ~4.4s
  POST /tenants:     p50 ~210-520ms, p95 ~280-600ms
  POST /auth/signup: p50 ~1.5s, p95 ~2.3-2.8s

=== Tenant isolation check under concurrency (60 tenants) ===
  GET /employees: p50 ~70-160ms, p95 ~170-250ms
  Result: PASS — every tenant saw only its own data

=== Per-tenant rate limiting check (burst=200) ===
  hammered tenant: 118 succeeded, 82 throttled (429) out of 200
  control tenant (different bucket): status=200 (OK)
  Result: PASS — throttling engaged, other tenant unaffected
```

Isolation and rate limiting both held at 40-60 concurrent tenants across
repeated runs. **118 successes before throttling** lines up almost exactly
with the gateway's configured 120-requests/60s budget — the rate limiter is
behaving exactly as designed.

## What the load test found (and what changed as a result)

Signup latency (`POST /auth/signup`) is the interesting number above: it's a
3-hop chain (auth-service → employee-service → agent-registry, each with its
own Postgres pool) and its p95 grew from sub-second at low concurrency to
2.3-2.8s once concurrency crossed ~30 in-flight requests. Two causes, both
addressed this phase:

1. **Connection pool sizing.** `libs/tenancy`'s `make_engine()` was using
   SQLAlchemy's bare defaults (`pool_size=5`, `max_overflow=10` — 15
   connections per engine per pod), sized for a single low-traffic instance,
   not a Deployment HPA can scale out under real load. Bumped to
   `pool_size=10`/`max_overflow=15` (25/pod) with `pool_recycle=1800`, tuned
   once in the shared helper so every service picks it up automatically (see
   the docstring in
   [`libs/tenancy/src/tenancy/session.py`](../libs/tenancy/src/tenancy/session.py)
   for the full reasoning). sqlite (used by every service's test suite)
   is left untouched — its `StaticPool` doesn't accept these kwargs at all.

2. **Argon2 hashing blocking the event loop.** `hash_password`/
   `verify_password` (argon2, deliberately CPU-heavy — that's the point of
   the algorithm) were being called directly inside `async def` routes,
   which runs pure-CPU work on the single event-loop thread and serializes
   *every* concurrent request in that process behind each hash, not just
   other auth calls. Added `hash_password_async`/`verify_password_async`
   (`asyncio.to_thread` wrappers) in
   [`libs/auth/src/auth/passwords.py`](../libs/auth/src/auth/passwords.py)
   and switched auth-service's signup/login routes to use them.

Both changes are real fixes, not just under-load micro-optimizations, and
both are covered by the existing test suites (355 tests passing
workspace-wide after the change). What repeated local runs on a single dev
laptop could **not** cleanly show is a large before/after wall-clock
improvement — a laptop running Docker, five Python processes, and the load
generator itself has too much of its own noise to isolate a clean signal at
this scale. The pooling fix is sound engineering regardless (SQLAlchemy's
defaults are genuinely too small for a multi-tenant HPA-scaled deployment);
the argon2 fix's real payoff is that CPU-bound hashing work no longer starves
*unrelated* concurrent requests on the same pod, which single-endpoint
before/after timing doesn't fully capture. The actual lever for CPU-bound
load at real scale is horizontal scaling — see the HPA section below — not
squeezing more out of one pod.

## Postgres connection budget

The shared Postgres instance (`infra/k8s/postgres.yaml`) backs 8 of the 9
Postgres-using services (everything except knowledge-service, which has its
own pgvector instance — see `infra/k8s/postgres-vector.yaml`). With the new
per-pod pool budget (25) and each service's own HPA `maxReplicas` (3-6, see
below), the theoretical worst case if every service's HPA maxed out
*simultaneously* is well over the default `max_connections=100`. Bumped to
`max_connections=300` on the shared instance and `150` on the vector one —
deliberately not sized for "every service peaks at once" (unrealistic:
different tenants' business hours, different workloads), but for a
realistic multi-tenant load shape. A real production deployment at
sustained high tenant counts should put PgBouncer in front of Postgres
rather than raising `max_connections` further — noted as a follow-up, not
built this phase.

## k8s HPA

Added `HorizontalPodAutoscaler` manifests for all 12 services (none existed
before Phase 10 — phase 6 only shipped Deployments/Services, despite the
phase 10 prompt's framing that assumed they already existed; verified via
`find infra/k8s -iname "*hpa*"` returning nothing before this work).
CPU-based (`autoscaling/v2`, `Resource`/`cpu`/`Utilization`), since every
Deployment already sets `resources.requests.cpu` (required for HPA to
compute utilization at all) from phase 6. `minReplicas` matches each
Deployment's existing static `replicas:` field; `maxReplicas` and CPU target
vary by role:

| Service | min | max | target | why |
|---|---|---|---|---|
| api-gateway | 2 | 8 | 65% | front door for all traffic, already ran >1 replica pre-HPA |
| tenant-service | 1 | 6 | 70% | signup/provisioning chain, proven hot by this load test |
| employee-service | 1 | 6 | 70% | same chain |
| auth-service | 1 | 6 | 70% | signup/login argon2 hashing — HPA is the real scaling lever here |
| agent-registry | 1 | 6 | 70% | called on every signup and every chat turn |
| llm-gateway | 1 | 8 | 75% | every chat turn and tool-call round-trip |
| openclaw-runtime | 1 | 8 | 75% | the core chat hot path |
| memory-service | 1 | 4 | 75% | on the chat hot path but lightweight (Postgres-only) |
| knowledge-service | 1 | 4 | 75% | retrieval read path is hot; upload/embed is bursty but rare |
| skill-marketplace | 1 | 4 | 75% | scales with enabled skills, not every chat turn |
| analytics-service | 1 | 3 | 75% | mostly an event consumer + read-only dashboards |
| audit-service | 1 | 3 | 75% | append-only writes + event consumer |

All twelve `HorizontalPodAutoscaler` manifests parse and validate as correct
YAML (`yaml.safe_load_all` over every file in `infra/k8s/`); actually
exercising HPA's scale-out behavior end-to-end needs a real cluster with
metrics-server, which is out of reach in this environment — the manifests
themselves, and the CPU-request baseline they depend on, are what's verified
here.

## Reproducing

```bash
docker compose up -d postgres redis rabbitmq
# run migrations + start tenant-service, employee-service, auth-service,
# agent-registry, api-gateway (see README's "Local dev" section)
uv run python scripts/load_test.py --tenants 60 --concurrency 30 --rate-limit-burst 200
```
