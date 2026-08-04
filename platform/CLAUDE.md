# Project: Multi-Tenant Enterprise AI Agent Platform (powered by OpenClaw)

Cloud-native, multi-tenant SaaS platform that provisions a personal AI agent
for every employee of every signed-up organization. OpenClaw is the agent
orchestration/runtime engine; everything else in this repo is the enterprise
platform layer around it (tenancy, identity, knowledge, memory, governance,
integrations, billing, observability).

Strategic note: OpenClaw is an implementation detail. The platform —
tenant isolation, enterprise identity, governance, billing, observability,
and integrations — is the actual product.

## Build phase (update this as phases complete)

Current phase: **8 — Skill Marketplace + first connectors (Slack, Google Calendar)**

Do not implement components outside the current phase unless explicitly asked.
Phases:

0. Monorepo scaffold, CI, local docker-compose (Postgres, Redis)
1. Tenant Service + Employee Service, tenant_id isolation pattern
2. Basic auth: email/password + JWT (SSO providers deferred to phase 9)
3. Agent Registry + LLM Gateway (Claude only for now) + OpenClaw wiring
4. Memory Service (Postgres only; vector DB deferred)
5. Knowledge Platform: PDF/DOCX upload + pgvector
6. API Gateway, containerize, deploy to single k8s namespace
7. Analytics Service (usage, tokens, cost)
8. Skill Marketplace + first connectors (Slack, Google Calendar)
9. SSO providers (Google Workspace, Entra ID, Okta, Auth0, LDAP), RBAC/ABAC, audit logging
10. Remaining connectors, multi-provider LLM Gateway, full-scale multi-tenancy

## Non-negotiable architectural rule: tenant isolation

Every table has a `tenant_id` column. Every query must filter on it —
no exceptions, no "trusted" internal calls that skip it. Implement this as
a shared ORM base / query middleware that injects `WHERE tenant_id = ?`
automatically, so a hand-written query literally cannot forget it. Any PR
that queries a tenant-scoped table without going through that layer should
be flagged.

## Core request flow (implement in this order, phase 3+)

Employee message → API Gateway → Authentication → Identify Tenant →
Identify Employee → Load Agent → Load Memory → Load Knowledge →
Load Skills → OpenClaw Runtime → LLM → Tool Calls → Generate Response →
Store Memory → Return Response

OpenClaw itself is stateless — it loads memory, skills, prompt, and
knowledge fresh on every request. Do not add hidden state to the runtime.

## Component reference

| Component | Responsibility | Phase |
|---|---|---|
| Authentication Service | Login, registration, SSO, OAuth, MFA, JWT | 2 / 9 |
| Tenant Service | Tenant CRUD, isolation, plan, billing, limits | 1 |
| Employee Service | Employee CRUD, AD/Google Workspace sync | 1 |
| Agent Registry | One agent profile per employee (model, prompt, temperature, memory namespace, knowledge sources, skills, permissions) | 3 |
| Memory Service | Per-employee isolated memory: conversation, long-term, preferences, facts, learned behaviour | 4 |
| Knowledge Platform | Company / department / personal knowledge; sources: PDF, DOCX, SharePoint, Drive, Confluence, Notion, web, DB | 5 |
| Skill Marketplace | Reusable plugins (CRM, SAP, Salesforce, Jira, GitHub, Slack, WhatsApp, Calendar, Email, ERP, HRMS), tenant-enabled per-skill | 8 |
| OpenClaw Runtime | Stateless agent execution: tool calling, planning, reasoning, context assembly | 3 |
| LLM Gateway | Provider abstraction (Claude, GPT, Gemini, Llama, Mistral, DeepSeek, local) | 3 (Claude only) / 10 (multi-provider) |
| Integration Platform | Enterprise connectors: SAP, Oracle, Salesforce, HubSpot, Teams, Slack, WhatsApp, Google Workspace, M365, ServiceNow, Jira, GitHub | 8 / 10 |
| Analytics Service | Usage, tokens, cost, conversation count, skill usage, agent health, productivity | 7 |

## Data model anchors

Core entities: Tenant, Employee, Department, Agent, Conversation, Memory,
Knowledge, Skill, Workflow, Documents, Subscription, Audit Log, Usage,
LLM Models, API Keys.

## Tech stack (defaults — don't substitute without asking)

- Frontend: React / Next.js — Mobile: Flutter
- Backend APIs: FastAPI or NestJS (pick one and stay consistent)
- Agent runtime: OpenClaw
- Auth: Keycloak / Auth0 / Microsoft Entra ID
- DB: PostgreSQL — Cache: Redis — Vector DB: Qdrant or pgvector
- Object storage: S3 / GCS / MinIO
- Message queue: Kafka or RabbitMQ
- Workflow engine: Temporal or OpenClaw Workflows
- Orchestration: Kubernetes (GKE / EKS / AKS)
- Observability: Prometheus + Grafana, Loki + OpenTelemetry
- CI/CD: GitHub Actions + ArgoCD
- LLM Gateway: LiteLLM or a custom gateway

## Security baseline (apply from phase 0, don't defer)

- TLS everywhere, AES-256 at rest
- Secrets in Vault / GCP Secret Manager / AWS Secrets Manager — never in env files committed to git
- Every state-changing action gets an audit log entry
- RBAC from phase 1; ABAC added in phase 9

## Conventions for this repo

- One service, one directory, one clear ownership boundary — no shared
  mutable state between services outside the message queue / DB.
- Every new tenant-scoped table needs a migration that includes `tenant_id`
  with an index, no exceptions.
- Prefer boring, explicit code over cleverness — this is infrastructure
  many tenants depend on.
- When adding a new connector or skill, follow the existing plugin
  interface rather than special-casing it into the core runtime.
