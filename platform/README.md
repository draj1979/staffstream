# StaffStream Platform

Multi-tenant enterprise AI agent platform (powered by [OpenClaw](https://github.com)).
OpenClaw is the agent orchestration/runtime engine; this repo is the
enterprise platform layer around it — tenancy, identity, knowledge, memory,
governance, integrations, billing, observability.

See [CLAUDE.md](./CLAUDE.md) for architecture, build phases, and
conventions.

## Current phase

**Phase 10 — Remaining connectors, multi-provider LLM Gateway, and
full-scale multi-tenancy (complete).**

## Stack

- Backend APIs: FastAPI (Python 3.12), dependency/task management via [uv](https://docs.astral.sh/uv/)
- DB: PostgreSQL (one logical database per service) — Cache: Redis
- Migrations: Alembic — CI: GitHub Actions
- Auth: argon2 password hashing (off the event loop via `asyncio.to_thread`, see [Local development](#local-development)), HS256 JWT access tokens (embed a `role` claim), opaque hashed refresh tokens
- SSO: OIDC (Google Workspace, Auth0) mapped onto the existing employee_id/tenant_id model — no parallel identity system
- LLM: Claude, GPT, Gemini, Mistral, DeepSeek, and Llama (via Groq) behind one provider-abstraction interface, with tool-calling and per-tenant/agent model selection
- Embeddings: Voyage AI (`voyage-3-lite`, 512-dim) — Vector DB: pgvector
- Containers: one Dockerfile per service — Orchestration: Kubernetes (single namespace, HPA on every service)
- Events: RabbitMQ (topic exchange) — LLM usage / chat interaction / skill usage / audit events
- Connectors: Slack, Google Calendar, Salesforce, HubSpot, Jira, GitHub, Microsoft Teams, Microsoft 365, ServiceNow, SAP, Oracle, WhatsApp — tokens encrypted at rest (Fernet)

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

Access tokens are short-lived JWTs (15 min default) carrying `tenant_id`,
`sub` (employee_id), and (Phase 9) `role` in the claims — see
[libs/auth/src/auth/jwt.py](libs/auth/src/auth/jwt.py). The role is always
re-fetched from Employee Service at token-mint time (login, refresh, SSO
callback), never cached, so a role change takes effect on the very next
token issuance, not whenever some cached copy happens to expire. Refresh
tokens are opaque random strings; only their SHA-256 hash is stored, so
they can be genuinely revoked (unlike a stateless JWT, which can't be
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

Phase 10 adds an `Agent.provider` column (default `"claude"`) alongside the
existing `model` field, so the LLM Gateway's provider name and model name
travel together on the agent, not just the model. Employee Service reads a
tenant's default provider/model off `Tenant.llm_config` (a widened
`GET /tenants/{id}` now also accepts a system-scoped token, not just a user
one) at agent-creation time and passes them through — falling back silently
to Agent Registry's own hardcoded default if the tenant has none set or
Tenant Service is unreachable, rather than blocking employee creation over it.

## LLM Gateway

`services/llm-gateway` is a thin, authenticated `POST /generate` in front of
an internal `Provider` interface
([provider.py](services/llm-gateway/src/llm_gateway/provider.py)) and an
`LLMGateway` registry that dispatches by provider name.

Phase 10 registers six providers: `"claude"` (the official Anthropic SDK,
its own bespoke `Provider`) plus `"openai"`, `"gemini"`, `"mistral"`,
`"deepseek"`, and `"llama"` — all five of the latter share one
[`OpenAICompatibleProvider`](services/llm-gateway/src/llm_gateway/providers/openai_compatible.py)
implementation (raw `httpx`, OpenAI's Chat Completions wire format),
parameterized by `base_url`/`api_key`, since GPT natively speaks that format
and Mistral/DeepSeek/Groq(-hosted Llama)/Google(Gemini, via its documented
OpenAI-compatibility endpoint) all support an equivalent-enough one. That
avoided writing five near-duplicate provider classes and four extra SDK
dependencies. Per-tenant/agent model selection (see Agent Registry above)
picks which of the six a given chat turn uses; `pricing.py` has cost-per-token
entries for all six providers' models, feeding the same Phase 7 Analytics
cost pipeline regardless of which provider actually served the request.

**Known limitation:** OpenClaw Runtime's tool-calling loop (Phase 8) builds
Anthropic-shaped message content blocks (`tool_use`/`tool_result`), so a
*full* multi-turn tool conversation only round-trips correctly with the
Claude provider today. Every provider can receive tool definitions and
return `tool_calls` for one turn — only *continuing* that conversation
across turns needs a translation layer this phase didn't build. Documented
here and in
[`openai_compatible.py`](services/llm-gateway/src/llm_gateway/providers/openai_compatible.py)'s
docstring rather than silently shipped as if it worked.

Phase 8 adds tool-calling to the request/response contract: `LLMRequest`
takes an optional `tools` list (Anthropic's name/description/input_schema
shape), and `LLMResponse.tool_calls` carries back any `tool_use` blocks the
model produced (`stop_reason: "tool_use"`), alongside the usual text
`content` — see [models.py](services/llm-gateway/src/llm_gateway/models.py).
The gateway itself doesn't execute tools; it just passes the tool
definitions through to the provider and structures the response. OpenClaw
Runtime is what actually runs a tool and feeds the result back.

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
Registry, Memory Service, LLM Gateway, and Skill Marketplace rather than
minting a new one — the caller already has a valid session, so there's no
separate identity to establish.

Phase 8 adds the "Load Skills -> LLM -> Tool Calls" part of CLAUDE.md's
request flow ([skills.py](services/openclaw-runtime/src/openclaw_runtime/skills.py),
the tool loop in `runtime.py`): before calling the LLM, it fetches the
tools Skill Marketplace has available for this employee (already filtered
to tenant-enabled + employee-connected) and narrows that further to the
agent's own `skills` allowlist from Agent Registry — three independent
gates that all have to agree before a tool ever reaches the LLM. If the
model responds with a `tool_use` block, the runtime invokes the matching
skill via Skill Marketplace, feeds the result back as a `tool_result`, and
loops (bounded by `MAX_TOOL_ITERATIONS = 5`) until the model returns a
plain text reply. Every tool call — success or failure — publishes a
`SkillUsageEvent` the same fire-and-forget way as chat interaction events.

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

## API Gateway

`services/api-gateway` is the one front door — every other service's
Service should stay ClusterIP-only in a real deployment; this is the only
one meant to be reachable from outside the cluster (see its k8s manifest).
It reverse-proxies by path prefix (`/tenants` -> Tenant Service, `/chat` ->
OpenClaw Runtime, etc. — see
[routing.py](services/api-gateway/src/api_gateway/routing.py)) and adds
three things no individual backend service has on its own:

- **Per-tenant rate limiting** — a Redis-backed fixed-window counter
  ([rate_limit.py](services/api-gateway/src/api_gateway/rate_limit.py)),
  keyed by the `tenant_id` claim from the caller's JWT (verified, so a
  client can't dodge its own limit by forging the claim), falling back to
  the `X-Tenant-Id` header or the client IP for pre-auth routes like
  signup. One tenant maxing out its quota never touches anyone else's
  bucket. This is deliberately *not* an authorization check — the gateway
  never rejects a request for a missing/invalid/expired token; that's
  still each backend's own `require_auth`, exactly as before.
- **Request size limits** — a fast `Content-Length` pre-check plus a real
  streaming byte-count guard (so a lying header can't bypass it), with a
  much higher ceiling for knowledge-service's upload path than everywhere
  else.
- **Centralized error sanitization** — any 5xx from a backend (or a
  proxying failure like a timeout) gets its body replaced with a generic
  `{"detail": "..."}` message before it ever reaches the client; whatever
  the backend actually said — stack trace, DB error text, anything — is
  logged server-side and never forwarded. 4xx responses pass through
  unchanged, since those are messages the backend already wrote to be
  client-safe.

## Analytics Service

`services/analytics-service` never sits on the `/chat` request path — it's
fed asynchronously so LLM Gateway/OpenClaw latency is never coupled to
analytics ingestion. [libs/events](libs/events) defines the shared event
schemas and a thin `aio-pika`-based pub/sub wrapper over a RabbitMQ topic
exchange (`staffstream.events`):

- **LLM Gateway** publishes an `LLMUsageEvent` (tenant, employee, agent,
  provider, model, input/output tokens, `cost_usd` from
  [pricing.py](services/llm-gateway/src/llm_gateway/pricing.py)) after
  every successful `/generate` call.
- **OpenClaw Runtime** publishes a `ChatInteractionEvent` (tenant,
  employee, agent, success/failure, which stage failed if any, latency)
  after every `/chat` call, success or failure — agent attribution
  survives even a downstream failure via a small `TurnContext` object
  threaded through the call.

Both publish sites use `asyncio.create_task` (never awaited by the route
handler) with a strong reference kept in `app.state.background_tasks`, and
swallow their own publish failures internally — a RabbitMQ outage degrades
analytics, never the chat/generate response. Analytics Service's own
consumers ([consumer.py](services/analytics-service/src/analytics_service/consumer.py))
reconnect with exponential backoff and set the tenant context straight
from the event payload (there's no JWT on a queue message) before writing
a row; a message that fails to parse is logged and dropped rather than
redelivered forever (documented as a known simplification — no
dead-letter queue yet).

Three read endpoints aggregate at query time (`crud.py`) per the HLD's
dashboard split — `GET /analytics/admin` (conversation count, success
rate, active employees/agents, token/cost totals), `/analytics/finance`
(cost by model, by employee, daily trend), and `/analytics/it` (error
rate, avg/p95 latency, per-agent health, errors by failure stage) — all
behind `require_auth()` and tenant-scoped through the same tenancy layer
as everything else, with `from_date`/`to_date` query params defaulting to
a trailing 30-day window. Role-gating which dashboard an employee can see
is RBAC, deferred to Phase 9 like everywhere else in the platform.
`SkillUsageEventRow`/`SkillUsageEvent`'s producer landed in Phase 8 —
OpenClaw Runtime publishes one per tool call, ingested by the same
consumer pattern as the other two event types (see
[consumer.py](services/analytics-service/src/analytics_service/consumer.py)).
The three dashboard endpoints don't surface skill usage yet — the data
lands in Postgres and is queryable, but `crud.py`'s aggregations weren't
extended for it this phase.

## Skill Marketplace

`services/skill-marketplace` is a registry of skills (`Skill`, a shared
catalog — not tenant-scoped, seeded by its migration) plus two
tenant/employee-scoped tables: `TenantSkillEnablement` (opt-in per tenant,
`enabled` + `config`, never on by default) and `EmployeeConnection` (one
employee's own OAuth grant for one skill — access/refresh tokens Fernet-
encrypted at rest, keyed by `(tenant_id, employee_id, skill_id)`, never
shared with anyone else in the tenant).

Each skill is a [`Connector`](services/skill-marketplace/src/skill_marketplace/connectors/base.py)
implementation registered in `CONNECTOR_REGISTRY` by skill_id — nothing
elsewhere in the service imports a connector class directly, matching the
platform convention of not special-casing new skills into core logic:

- **Slack** ([slack.py](services/skill-marketplace/src/skill_marketplace/connectors/slack.py)) —
  OAuth v2 with `user_scope` (not `scope`): every token minted is a *user*
  token, so every API call this connector makes runs as the employee
  themselves, against whatever channels their own Slack account can see.
  Tools: `slack_list_channels`, `slack_read_channel_messages`,
  `slack_post_message`.
- **Google Calendar** ([google_calendar.py](services/skill-marketplace/src/skill_marketplace/connectors/google_calendar.py)) —
  OAuth2 with `access_type=offline` + `prompt=consent` for a refresh
  token; every call reads/writes the `primary` calendar of whichever
  account the token belongs to. Tools: `calendar_list_events`,
  `calendar_create_event`. Access tokens are refreshed automatically
  ahead of expiry (`crud.token_needs_refresh`) before a call is made.

Three gates all have to hold before a tool call actually reaches Slack or
Google, checked cheapest-first in
[routers/invoke.py](services/skill-marketplace/src/skill_marketplace/routers/invoke.py):
the skill has to exist, the tenant has to have it enabled, and *this*
employee has to have their own connection for it. Even then, the final
authorization boundary is the provider itself — nothing this service does
can make a call succeed that the employee's own OAuth grant doesn't
already permit at Slack/Google's end; there's no shared or elevated
credential anywhere in the path.

The OAuth flow itself (`GET /connections/{skill_id}/authorize` — a 307 to
the provider — and `GET /connections/{skill_id}/callback`) doesn't go
through `require_auth`, since the provider's redirect back carries no
bearer token. Instead, `/authorize` mints a short-lived signed `state`
token (`auth.encode_state_token`, added this phase alongside the existing
access/system tokens) carrying `tenant_id`/`employee_id`/`skill_id`, and
`/callback` trusts only what it can verify out of that token — never
anything from the request's own query string.

### Phase 10 connectors

Ten more skills, same `Connector` interface and same three-gate
authorization path above — no new pattern per connector, per CLAUDE.md:

- **Salesforce, HubSpot, Jira, GitHub** — one fixed global OAuth endpoint
  each, just like Slack/Google Calendar. Jira and Salesforce hand back
  extra data during token exchange (a `cloud_id` / `instance_url`) that
  every later API call needs — carried in `TokenSet.extra` and persisted
  on a new `EmployeeConnection.connection_metadata` column, then handed
  back to `invoke()` as `extra` on every call.
- **Microsoft Teams, Microsoft 365** — share one Entra ID app registration
  and Graph API; the common OAuth mechanics live in a private
  `_microsoft.py` helper (not itself a registered connector) so the two
  connectors don't duplicate ~80 lines of identical OAuth code.
- **ServiceNow, SAP, Oracle** — these don't have one fixed OAuth endpoint
  at all; each tenant's instance/landscape URL (`instance`, `sap_base_url`,
  `oracle_base_url`) is a tenant-level fact, not a per-deployment one, so
  it's read from `TenantSkillEnablement.config` — the same table Phase 8
  already introduced for per-tenant skill config — via a new
  `tenant_config: dict` parameter threaded through `authorize_url`/
  `exchange_code`/`refresh`. An admin sets it once via
  `PUT /skills/{skill_id}/enablement`.
- **WhatsApp** — Meta/WhatsApp Business Platform OAuth; needs a tenant-level
  `phone_number_id` (also from `tenant_config`) to know which WABA number
  to send from.

Both extension points (`tenant_config` and `TokenSet.extra`/`invoke`'s
`extra`) are additive, optional parameters on the existing `Connector` ABC
— Slack and Google Calendar's implementations didn't change behavior, only
their signatures widened to accept (and ignore) the new params.

## RBAC & ABAC

Three fixed roles, ranked `admin > manager > employee`
([libs/auth/src/auth/roles.py](libs/auth/src/auth/roles.py)) — scoped per
tenant by construction, since `role` only ever means something relative
to the token's own `tenant_id`. `require_role(minimum)`
([libs/auth/src/auth/dependency.py](libs/auth/src/auth/dependency.py))
composes `require_auth` with a hierarchy check ("at least this rank", not
an exact match) and is the one dependency every RBAC-gated route uses:

| Action | Minimum role |
|---|---|
| `PATCH /tenants/{id}` (tenant settings) | admin |
| `POST`/`PATCH /employees` via a user token (not the signup bootstrap) | manager |
| Changing an employee's `roles` | admin |
| `GET /agents` (list every agent in the tenant) | manager |
| `PATCH /agents/{id}` for someone else's agent | admin |
| `PUT /skills/{id}/enablement` | admin |
| `PUT /auth/sso/config/{provider}` | admin |

A `manager`-ranked token gets a further ABAC check on top of the role
check, in [employee_service/routers/employees.py](services/employee-service/src/employee_service/routers/employees.py):
they may only create or update employees whose `department` matches
their own (looked up fresh from their own Employee row on every request,
never cached), and they can never change an employee's `department` or
`roles` at all — only an admin can move someone between departments or
grant/revoke a role. An `admin` bypasses the department check entirely.
Department-scoped **knowledge** access from Phase 5 (personal + own
department + company-wide) is the other ABAC example already in the
platform — nothing new needed there this phase, just cited as the
pattern this phase's checks follow.

Agent Registry applies simpler ownership-or-role gating rather than
department ABAC: an employee can always read/update their own agent;
`manager`+ can read anyone's; only `admin` (or the employee themselves)
can edit someone else's — see
[agent_registry/routers/agents.py](services/agent-registry/src/agent_registry/routers/agents.py).

## SSO

`services/auth-service` gained `services/auth-service/src/auth_service/oidc.py`
— one generic OpenID Connect implementation shared by both providers
(Google Workspace and Auth0 are both standard OIDC; a provider only
differs in its discovery URL and Google's optional `hd` hosted-domain
restriction). Every network call (discovery, token exchange, JWKS fetch)
takes the httpx client to use rather than making its own, so tests
exercise real RS256 signature verification against a test keypair
through `httpx.MockTransport`, not a mocked-away crypto layer.

Each tenant configures their own IdP — `SsoConnection`
(tenant-scoped, `client_secret` Fernet-encrypted at rest, same pattern as
Skill Marketplace's OAuth tokens) — via `PUT /auth/sso/config/{provider}`
(admin-only). `GET /auth/sso/login/{tenant_id}/{provider}` redirects to
the IdP with a signed state token (`auth.encode_state_token`, same
mechanism as Skill Marketplace's OAuth state); `GET /auth/sso/callback/{provider}`
verifies the id_token's signature, issuer, and audience, then maps the
verified email straight onto Employee Service's existing
`(tenant_id, employee_id)` model via `GET /employees/by-email/{email}` —
**no parallel identity system**, and deliberately **no JIT auto-
provisioning** this phase: if no employee matches, the callback 404s
rather than minting a new one. An admin creates the employee record
first (same as any other employee), then that person can log in via SSO.
The role embedded in the resulting token comes from that employee's
current `roles`, exactly like password login.

The Phase 2 email/password path (`/auth/signup`, `/auth/login`,
`/auth/refresh`, `/auth/logout`) is completely untouched and still the
default — SSO is an additional login path per tenant, not a replacement.

## Audit Logging

`services/audit-service` (port 8011) stores an immutable, tenant-scoped
log of every state-changing action across the platform — employee CRUD,
role changes, skill enablement, OAuth connect/revoke, and tenant settings
changes, per CLAUDE.md's security baseline. It follows the exact same
event-sourcing pattern Analytics Service established in Phase 7: a new
`AuditEvent` schema in [libs/events](libs/events), a `ROUTING_KEY_AUDIT`
routing key on the shared `staffstream.events` exchange, and a background
RabbitMQ consumer that writes one row per event. `AuditLogEntry`
(`tenant_id`, `actor_employee_id`, `action`, `target_type`, `target_id`,
`metadata`, `created_at`) has **no update or delete route anywhere in
this service** — not "soft-protected", just structurally incapable of it,
since `crud.py` never defines those functions. A real deployment should
also grant the service's DB role only `INSERT`/`SELECT` on this table, so
the immutability guarantee doesn't rest on "nobody wrote the route" alone.

Every producer publishes fire-and-forget via `events.schedule_publish` (a
new shared helper pulled out of the hand-written version LLM Gateway and
OpenClaw Runtime each had in Phases 7/8 — same `asyncio.create_task` +
`app.state.background_tasks` + swallow-and-log pattern, now factored out
since a fourth call site needed the identical dozen lines): Tenant
Service (`tenant.updated`), Employee Service (`employee.created`,
`employee.updated`, `employee.role_changed`), Agent Registry
(`agent.updated`), Skill Marketplace (`skill.enablement_changed`,
`skill.connected`, `skill.disconnected`), and Auth Service
(`sso.config_changed`).

`GET /audit-logs` (admin-only, tenant-scoped through the standard
tenancy layer) supports filtering by `action`, `target_type`,
`actor_employee_id`, and a `from_date`/`to_date` range. Not routed
through the API Gateway — an internal/admin-facing read API, same
precedent as Analytics Service.

## Containers & Kubernetes

Every service has its own `Dockerfile` (multi-stage, `uv`-based, built
from the repo root since this is a uv workspace — see any service's
Dockerfile for the exact command). `make docker-build` builds all twelve.
`infra/k8s/base/` has Deployment + Service manifests for all twelve plus the
namespace, ConfigMap, Secret template, and in-cluster Postgres/Redis/RabbitMQ —
see [infra/k8s/README.md](infra/k8s/README.md) for the full deploy flow.
`infra/k8s/overlays/gcp/` layers Secret Manager + Cloud SQL on top of that
same base for a real GCP deployment — see
[docs/gcp-deployment.md](docs/gcp-deployment.md) for how that overlay,
`infra/terraform/gcp`, and the GitHub Actions deploy workflow fit
together.
Every Deployment's `livenessProbe` hits `/healthz` (process alive — never
checks dependencies, so a DB blip doesn't get the pod restarted) and its
`readinessProbe` hits `/readyz` (DB-backed services actually check DB
connectivity; stateless ones just confirm the process is up) — so k8s
stops routing traffic to a pod that can't actually serve, without
restarting a pod that just needs its dependency to come back.

### Scaling (Phase 10)

Every one of the twelve services now has a `HorizontalPodAutoscaler`
(CPU-based, `autoscaling/v2`) alongside its Deployment — none existed
before this phase. `minReplicas` matches each Deployment's static
`replicas:`; `maxReplicas` and CPU target vary by how central the service
is to the request hot path (2-8 replicas, 65-75% CPU target — see
[docs/phase10-load-test.md](docs/phase10-load-test.md) for the full table
and reasoning per service).

`libs/tenancy`'s `make_engine()` sizes each service's Postgres connection
pool (`pool_size=10`/`max_overflow=15` per pod, Postgres URLs only —
sqlite in tests is untouched) — bumped up from SQLAlchemy's single-instance
defaults after a load test showed them queuing under concurrent multi-tenant
traffic. The shared Postgres instance's `max_connections` (`infra/k8s/base/postgres.yaml`)
is bumped to match. `scripts/load_test.py` drives many concurrent tenants
through the real API Gateway and asserts tenant isolation and per-tenant
rate limiting both hold under that concurrency — see
[docs/phase10-load-test.md](docs/phase10-load-test.md) for results and how
to reproduce it locally.

## Local development

```bash
cp .env.example .env
make up       # start Postgres + Redis + Postgres/pgvector + RabbitMQ via docker-compose
make migrate  # run Alembic migrations for every service with a database
make lint     # ruff
make test     # pytest (fast, sqlite-backed where possible; Knowledge Service
              # skips cleanly without a live Postgres+pgvector, libs/events
              # skips cleanly without a live RabbitMQ; nothing ever calls the
              # real Anthropic or Voyage AI APIs)
make run-tenant-service     # http://localhost:8001
make run-employee-service   # http://localhost:8002
make run-auth-service       # http://localhost:8003
make run-agent-registry     # http://localhost:8004
make run-llm-gateway        # http://localhost:8005
make run-openclaw-runtime   # http://localhost:8006
make run-memory-service     # http://localhost:8007
make run-knowledge-service  # http://localhost:8008
make run-api-gateway        # http://localhost:8000
make run-analytics-service  # http://localhost:8009
make run-skill-marketplace  # http://localhost:8010
make run-audit-service      # http://localhost:8011
make down     # stop containers

make docker-build   # build all 12 service images (staffstream/<service>:latest)
```

To try the whole platform containerized rather than via `make run-*`, see
[infra/k8s/README.md](infra/k8s/README.md) — or run individual images
directly with `docker run` (each `Dockerfile`'s header comment has the
exact build command).

Postgres is exposed on host port **5433** (not 5432) to avoid clashing with
any other local Postgres instance; Knowledge Service's separate
Postgres+pgvector instance is on **5434** (a dedicated container, not a
retrofit of the shared one — see `docker-compose.yml`'s `postgres-vector`
service). `JWT_SECRET_KEY` must be identical across every service — see
`.env.example`. `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` — and, as of Phase
10, `OPENAI_API_KEY` / `GEMINI_API_KEY` / `MISTRAL_API_KEY` /
`DEEPSEEK_API_KEY` / `LLAMA_API_KEY` — are only needed to actually call
that provider; without them the services still start and route correctly,
calls just fail with a normal auth error from the provider. Same story for
`SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`/
`GOOGLE_CLIENT_SECRET`, and the ten Phase 10 connector client id/secret
pairs (`SALESFORCE_*`, `HUBSPOT_*`, `JIRA_*`, `GITHUB_*`, `MICROSOFT_*`,
`SERVICENOW_*`, `SAP_*`, `ORACLE_*`, `WHATSAPP_*`) — Skill Marketplace
starts fine without any of them registered, an OAuth authorize/exchange
just fails with a normal error from the provider until they're set.
`OAUTH_ENCRYPTION_KEY` / `SSO_ENCRYPTION_KEY`
have working local-dev defaults but should each be regenerated per real
environment (see `.env.example`'s comment for the one-liner). SSO itself
needs no service-level credentials at all to start — each tenant supplies
their own Google Workspace/Auth0 client ID and secret via
`PUT /auth/sso/config/{provider}` at runtime, not an env var.

## Layout

```
libs/
  tenancy/            shared tenant-isolation ORM base + session middleware
  auth/                shared JWT issuance/verification (incl. role claim + require_role RBAC), password hashing, signed state tokens
  events/              shared event schemas + RabbitMQ pub/sub (publisher, consumer, schedule_publish)
services/
  tenant-service/      Tenant CRUD: plan, storage quota, LLM config, branding, subscription — admin-only updates
  employee-service/    Employee CRUD: department, designation, manager, roles, agent_id — RBAC + department ABAC
  auth-service/        Signup/login/refresh/logout (password) + SSO (Google Workspace, Auth0) — the only service touching credentials
  agent-registry/      One agent profile per employee: model, prompt, temperature, memory namespace, ...
  llm-gateway/          Provider abstraction over LLMs: Claude, GPT, Gemini, Mistral, DeepSeek, Llama — emits LLM usage events
  openclaw-runtime/     Stateless: POST /chat — loads agent + memory + knowledge + skills, tool-calling loop, emits chat/skill events
  memory-service/       Per-employee memory: conversation, long-term, preferences, learned facts
  knowledge-service/    Company/department/personal knowledge: PDF/DOCX -> chunks -> pgvector
  api-gateway/          Front door: per-tenant rate limiting, size limits, sanitized errors, reverse proxy
  analytics-service/    Usage/tokens/cost/health from queued events — Admin/Finance/IT dashboards
  skill-marketplace/    Skill registry, per-tenant enablement, per-employee OAuth (12 connectors)
  audit-service/        Immutable, tenant-scoped audit trail of every state-changing action
tests/                 root-level smoke tests
docs/                  architecture and design docs
scripts/               load_test.py — multi-tenant concurrency + rate-limit load test (Phase 10)
infra/
  docker/               docker-compose init scripts
  k8s/                  Deployment/Service/HorizontalPodAutoscaler/ConfigMap/Secret manifests, single namespace
    base/                 the local/kind deployment (Phase 6's original scope)
    overlays/gcp/          GCP deployment: Secret Manager CSI + Cloud SQL Auth Proxy patches on top of base/
  terraform/gcp/        GCP infra as code: VPC, Cloud SQL, Memorystore, GKE Autopilot, Artifact Registry, Secret Manager, Workload Identity Federation
```

Every service directory also has its own `Dockerfile`.
