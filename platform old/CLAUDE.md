# StaffStream — Claude Code Project Memory

> This file is the authoritative context document for all Claude Code sessions on the StaffStream project.
> Read this fully before touching any file. Update it when significant architectural decisions are made.

---

## What this project is

**StaffStream** (`staffstream.in`) is an AI Workforce Orchestration Platform — a multi-tenant SaaS that deploys role-aware AI assistants for every employee in an enterprise, governed by org-chart structure, policy engine, and human-in-the-loop approval workflows.

Built by **Kartavya Technology** (official Anthropic partner) for the India-first enterprise market.

**Core thesis:** Generic AI tools don't understand org charts. StaffStream mirrors the org chart inside an AI layer — every assistant knows its role, department, reporting line, KPIs, and who it can and cannot talk to.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend API | Next.js API routes + Node.js microservices |
| Database | Neon (dev) → AWS RDS PostgreSQL (prod), row-level security with `company_id` |
| Cache / Message bus | AWS ElastiCache (Redis Streams) |
| Agent runtime | OpenClaw (one pod per agent), managed via Kubernetes (EKS) |
| Agent orchestration | Lobster (YAML workflow engine within OpenClaw) |
| MCP bridge | MCPorter (within OpenClaw) |
| Policy engine | Open Policy Agent (OPA) with Rego |
| Secret management | AWS Secrets Manager |
| Auth | Auth0 (SSO/SAML for enterprise tenants) |
| Infra | AWS Mumbai (ap-south-1): EKS, ECS Fargate, RDS, ElastiCache, S3, CloudFront |
| CI/CD | AWS CodePipeline + ECR |

---

## Three-tier architecture

```
Tier 1 — SaaS Platform (Next.js)
  Admin Console | Employee Portal | Skill Marketplace | MCP Registry

Tier 2 — Governance Engine (Node.js microservices)
  Policy Engine (OPA) | Message Bus (Redis Streams) | Hierarchy Enforcer

Tier 3 — OpenClaw Agent Fleet (EKS pods)
  One OpenClaw pod per employee, isolated per tenant namespace
```

---

## Repository structure

```
staffstream/
├── CLAUDE.md                    ← YOU ARE HERE — read first every session
├── apps/
│   ├── web/                     ← Next.js app (Tier 1)
│   │   ├── app/                 ← App Router pages
│   │   │   ├── (admin)/         ← Admin console routes
│   │   │   ├── (employee)/      ← Employee portal routes
│   │   │   ├── api/             ← API route handlers
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   ├── employee/
│   │   │   └── ui/              ← Shared UI components
│   │   └── lib/
│   │       ├── db/              ← Neon/Postgres client, queries
│   │       ├── auth/            ← Auth0 helpers
│   │       └── api/             ← Internal API clients
│   └── governance/              ← Tier 2 Node.js microservices
│       ├── policy-engine/       ← OPA policy evaluation service
│       ├── message-bus/         ← Redis Streams router
│       └── hierarchy-enforcer/  ← Manager supervision daemon
├── packages/
│   ├── db/                      ← Shared DB schema, migrations (Drizzle ORM)
│   ├── types/                   ← Shared TypeScript types across apps
│   └── config/                  ← Shared ESLint, TSConfig, Tailwind config
├── infra/
│   ├── k8s/                     ← Kubernetes manifests (EKS)
│   │   ├── agent-pod-template.yaml
│   │   └── namespaces/
│   ├── terraform/               ← AWS infrastructure as code
│   └── docker/                  ← Dockerfiles
├── scripts/
│   ├── provision-agent.ts       ← Spins up a new OpenClaw pod for an employee
│   └── seed-db.ts               ← Dev database seeding
└── docs/
    ├── hld.md                   ← High-Level Design (reference)
    ├── api.md                   ← API contracts
    └── data-model.md            ← Entity definitions
```

---

## Core data model (PostgreSQL, row-level security on company_id)

```sql
Company       (id, name, code, subscription_tier, settings_json)
Department    (id, company_id, name, data_classification, kpis_json)
Role          (id, department_id, name, seniority_level, reports_to_role_id, default_skills[])
Agent         (id, role_id, human_employee_id, status, autonomy_mode, config_json, pod_id)
Employee      (id, company_id, email, name, auth_provider_id)
Skill         (id, name, version, trust_level, category, clawhub_ref, scan_status)
MCPConnection (id, company_id, name, type, server_url, secret_arn, allowed_roles[])
Policy        (id, scope, rego_rule, priority)
AuditLog      (id, agent_id, action_type, payload, result, timestamp, cost)
ApprovalRequest (id, agent_id, action_category, status, requested_at, resolved_at, resolver_id)
```

All tables have `company_id` and use Postgres RLS: `CREATE POLICY tenant_isolation ON table USING (company_id = current_setting('app.company_id')::uuid)`.

ORM: **Drizzle ORM** (type-safe, works well with Neon).

---

## Human-in-the-loop (HITL) — always implement these gates

Every consequential agent action must pause for human approval. Never skip these:

| Action | Approver | Timeout | Fallback |
|---|---|---|---|
| Skill installation | Employee (individual) or Admin (role-wide) | 24h | Cancel |
| First MCP tool invocation | Employee | 4h | Defer + remind |
| Cross-department message | Employee | 8h | Queue + notify |
| Action above cost threshold | Employee | 4h | Block |
| Confidential+ data sharing | Employee + Data Owner | 24h | Block + escalate |
| Org change (>10 agents) | Admin | 48h | Cancel |
| Agent termination | Admin | 48h | Continue + notify |

Approval flow: Agent posts to `ApprovalRequest` table → Employee Portal shows in approval queue → Employee approves/rejects → Lobster workflow resumes or cancels.

---

## Agent provisioning flow

When a virtual employee slot is assigned to a human employee:

1. Generate `openclaw.json` from role template (skills, MCP connections, system prompt)
2. Spin up Kubernetes pod in `tenant-{company_id}` namespace
3. Install skills via `clawhub install` (curated marketplace only, not raw ClawHub)
4. Configure MCP via MCPorter (scoped tokens from Secrets Manager, never raw credentials)
5. Register agent with Message Bus and Hierarchy Enforcer
6. Send invitation email to human employee

Script: `scripts/provision-agent.ts`

---

## Policy engine rules (OPA/Rego)

Policy evaluation order for inter-agent messages (highest priority first):
1. Platform-level hardcoded safety rules (never override)
2. Company-level policies (admin-set)
3. Department-level information barriers
4. Agent-level user policies (employee-set communication rules)
5. Data classification check on message payload

Policy files live in `apps/governance/policy-engine/policies/`.

---

## Message bus (Redis Streams)

All inter-agent communication routes through the Message Bus — agents never talk directly.

Stream keys: `agent:{agent_id}:inbound` and `agent:{agent_id}:outbound`
Message types: `REQUEST | RESPONSE | BROADCAST | ESCALATION | SUPERVISION`
Dead letter queue: `dlq:blocked-messages`
Retention: 90 days

---

## Skill marketplace — curated only

Never install raw ClawHub skills. All skills in the platform marketplace must pass:
1. Automated static scan (prompt injection, malicious patterns, unauthorized network calls)
2. Sandboxed behavioral analysis (no real credentials during test)
3. Human security review

Custom company skills: same scan pipeline, scoped to company tenant.

---

## OpenClaw security notes

- CVE-2026-25253 (CVSS 8.8): Always use OpenClaw v1.2.3+ — prevents command injection
- ClawHavoc campaign: ~12% of raw ClawHub skills found malicious in audits — never use unvetted skills
- Agents run with read-only filesystem, no root, restricted egress (whitelisted domains only)
- All credentials in Secrets Manager, never in openclaw.json

---

## Environment variables

```bash
# Database
DATABASE_URL=                    # Neon connection string (dev)
DATABASE_URL_PROD=               # RDS (prod)

# Auth
AUTH0_DOMAIN=
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=

# AWS
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Redis
REDIS_URL=                       # ElastiCache connection string

# Anthropic
ANTHROPIC_API_KEY=               # For Claude as LLM within agents

# OPA
OPA_SERVER_URL=                  # Open Policy Agent endpoint

# Internal
NEXT_PUBLIC_APP_URL=
AGENT_PROVISIONER_SECRET=        # Shared secret between web and provisioner
```

Never commit secrets. Use `.env.local` for development.

---

## Development commands

```bash
# Install dependencies
pnpm install

# Run all apps in development
pnpm dev

# Database migrations (Drizzle)
pnpm db:generate      # generate migration from schema changes
pnpm db:migrate       # apply migrations to Neon dev DB
pnpm db:studio        # open Drizzle Studio (DB browser)

# Run tests
pnpm test
pnpm test:e2e

# Lint + typecheck
pnpm lint
pnpm typecheck

# Provision a test agent (dev only)
pnpm tsx scripts/provision-agent.ts --employee-id=<id>

# Seed database with sample org structure
pnpm tsx scripts/seed-db.ts
```

---

## Coding standards

- **TypeScript strict mode** everywhere — no `any`, no `as unknown`
- **Functional components** in React, hooks over class components
- **Server Components** by default in Next.js App Router; `"use client"` only when needed
- **Drizzle ORM** for all database queries — no raw SQL unless migration files
- **Zod** for all runtime validation (API inputs, env vars, external data)
- **Error handling**: always use `Result<T, E>` pattern in service layer, never throw across module boundaries
- **API routes**: validate input with Zod, authenticate with Auth0 middleware, set `company_id` on DB session before any query
- **Naming**: `camelCase` for variables/functions, `PascalCase` for components/types, `SCREAMING_SNAKE_CASE` for constants, `kebab-case` for files
- **Comments**: write *why*, not *what*
- **Tests**: unit tests for all business logic in `governance/` services; integration tests for API routes

---

## Phase 1 MVP scope (current focus)

Building first. Do not scope creep into later phases:

- [x] Project scaffold and CLAUDE.md
- [ ] Database schema + Drizzle setup (Neon)
- [ ] Auth0 integration (company SSO)
- [ ] Admin console: company registration, department + role creation
- [ ] Agent provisioner: generates openclaw.json, spins up pod
- [ ] Employee portal: login, meet your assistant (chat UI via WebSocket)
- [ ] Basic KPI dashboard
- [ ] 5 curated skills pre-loaded in marketplace
- [ ] Approval queue (basic HITL gate for MCP invocations)

Phase 2 onwards: MCP Registry with Secrets Manager, policy engine, inter-agent messaging, hierarchy enforcer — do not build these yet.

---

## Key decisions log

| Date | Decision | Reason |
|---|---|---|
| Aug 2026 | Drizzle ORM over Prisma | Better Neon compatibility, lighter runtime |
| Aug 2026 | Neon for dev, RDS for prod | Neon serverless reduces dev infra cost; RDS gives production reliability in ap-south-1 |
| Aug 2026 | One OpenClaw pod per agent | Isolation, independent restarts, per-tenant namespace security |
| Aug 2026 | OPA/Rego for policy engine | Auditable, declarative, well-established in enterprise security stacks |
| Aug 2026 | Redis Streams over Kafka | Simpler ops at current scale; migrate to MSK if message volume requires |
| Aug 2026 | Auth0 over custom auth | SSO/SAML enterprise requirements; not worth building in-house |

---

## What NOT to build (ever in public-facing layer)

- Do not expose OpenClaw internals, Kubernetes details, or Redis architecture in the UI or docs
- Do not surface raw ClawHub marketplace — always use curated marketplace only
- Do not store raw credentials anywhere — always Secrets Manager
- Do not allow agents to self-install skills — always human approval required
- Do not build agent termination in the employee portal — admin only

---

## Contacts and context

- **Dharam Tiwari** — Co-Founder, tech lead (architecture, engineering)
- **Dharmendra Singh** — Co-Founder, business strategy
- **Ajit Ashwath** — Co-Founder, engineering
- **Company:** Kartavya Technology (official Anthropic partner)
- **Target customer:** Mid-size to large Indian enterprises (200+ employees), India-first
- **Seed raise:** $1M for 10% equity (in progress)
- **Compliance:** DPDP Act (India), roadmap to SOC 2 Type II and ISO 27001
- **Hosting:** AWS ap-south-1 (Mumbai) — data residency requirement, non-negotiable
