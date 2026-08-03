#!/bin/bash
# StaffStream — project scaffold script
# Run from the directory where you want the project created:
#   chmod +x scaffold.sh && ./scaffold.sh

set -e

echo "🚀 Scaffolding StaffStream monorepo..."

# ── Root ──────────────────────────────────────────────────────────────────────
mkdir -p staffstream && cd staffstream

cat > package.json << 'EOF'
{
  "name": "staffstream",
  "private": true,
  "scripts": {
    "dev": "turbo dev",
    "build": "turbo build",
    "test": "turbo test",
    "lint": "turbo lint",
    "typecheck": "turbo typecheck",
    "db:generate": "turbo db:generate",
    "db:migrate": "turbo db:migrate",
    "db:studio": "cd packages/db && pnpm drizzle-kit studio"
  },
  "devDependencies": {
    "turbo": "^2.0.0",
    "typescript": "^5.4.0",
    "@types/node": "^20.0.0"
  },
  "packageManager": "pnpm@9.0.0"
}
EOF

cat > turbo.json << 'EOF'
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "dev": { "persistent": true, "cache": false },
    "build": { "dependsOn": ["^build"], "outputs": [".next/**", "dist/**"] },
    "test": { "dependsOn": ["^build"] },
    "lint": {},
    "typecheck": { "dependsOn": ["^build"] },
    "db:generate": { "cache": false },
    "db:migrate": { "cache": false }
  }
}
EOF

cat > .gitignore << 'EOF'
node_modules/
.next/
dist/
.env
.env.local
.env*.local
*.tsbuildinfo
.turbo/
.DS_Store
EOF

cat > .env.example << 'EOF'
# Database
DATABASE_URL=postgresql://user:pass@host/staffstream

# Auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=
AUTH0_SECRET=                     # random 32-char string: openssl rand -hex 32

# AWS
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

# Redis
REDIS_URL=redis://localhost:6379

# Anthropic (for agent LLM)
ANTHROPIC_API_KEY=

# OPA policy engine
OPA_SERVER_URL=http://localhost:8181

# App
NEXT_PUBLIC_APP_URL=http://localhost:3000
AGENT_PROVISIONER_SECRET=         # random secret shared with provisioner service
EOF

# ── Shared packages ────────────────────────────────────────────────────────────
mkdir -p packages/{db,types,config}

# packages/db
cat > packages/db/package.json << 'EOF'
{
  "name": "@staffstream/db",
  "version": "0.0.1",
  "scripts": {
    "db:generate": "drizzle-kit generate",
    "db:migrate": "drizzle-kit migrate",
    "db:studio": "drizzle-kit studio"
  },
  "dependencies": {
    "drizzle-orm": "^0.30.0",
    "@neondatabase/serverless": "^0.9.0"
  },
  "devDependencies": {
    "drizzle-kit": "^0.21.0"
  },
  "exports": {
    ".": "./src/index.ts",
    "./schema": "./src/schema/index.ts"
  }
}
EOF

mkdir -p packages/db/src/schema

cat > packages/db/src/schema/index.ts << 'EOF'
export * from './company'
export * from './department'
export * from './role'
export * from './employee'
export * from './agent'
export * from './skill'
export * from './mcp-connection'
export * from './policy'
export * from './audit-log'
export * from './approval-request'
EOF

cat > packages/db/src/schema/company.ts << 'EOF'
import { pgTable, uuid, text, jsonb, timestamp, pgEnum } from 'drizzle-orm/pg-core'

export const subscriptionTierEnum = pgEnum('subscription_tier', ['starter', 'growth', 'enterprise'])

export const companies = pgTable('companies', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: text('name').notNull(),
  code: text('code').notNull().unique(),
  subscriptionTier: subscriptionTierEnum('subscription_tier').notNull().default('starter'),
  settingsJson: jsonb('settings_json').default({}),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/department.ts << 'EOF'
import { pgTable, uuid, text, jsonb, timestamp, pgEnum } from 'drizzle-orm/pg-core'
import { companies } from './company'

export const dataClassificationEnum = pgEnum('data_classification', [
  'public', 'internal', 'confidential', 'restricted'
])

export const departments = pgTable('departments', {
  id: uuid('id').primaryKey().defaultRandom(),
  companyId: uuid('company_id').notNull().references(() => companies.id, { onDelete: 'cascade' }),
  name: text('name').notNull(),
  dataClassification: dataClassificationEnum('data_classification').notNull().default('internal'),
  kpisJson: jsonb('kpis_json').default([]),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/role.ts << 'EOF'
import { pgTable, uuid, text, integer, timestamp } from 'drizzle-orm/pg-core'
import { departments } from './department'

export const roles = pgTable('roles', {
  id: uuid('id').primaryKey().defaultRandom(),
  departmentId: uuid('department_id').notNull().references(() => departments.id, { onDelete: 'cascade' }),
  name: text('name').notNull(),
  seniorityLevel: integer('seniority_level').notNull().default(1),
  reportsToroleId: uuid('reports_to_role_id'),   // self-reference: filled after insert
  defaultSkills: text('default_skills').array().default([]),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/employee.ts << 'EOF'
import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core'
import { companies } from './company'

export const employees = pgTable('employees', {
  id: uuid('id').primaryKey().defaultRandom(),
  companyId: uuid('company_id').notNull().references(() => companies.id, { onDelete: 'cascade' }),
  email: text('email').notNull(),
  name: text('name').notNull(),
  authProviderId: text('auth_provider_id'),       // Auth0 user ID
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/agent.ts << 'EOF'
import { pgTable, uuid, text, jsonb, timestamp, pgEnum } from 'drizzle-orm/pg-core'
import { roles } from './role'
import { employees } from './employee'

export const agentStatusEnum = pgEnum('agent_status', ['provisioning', 'active', 'paused', 'terminated'])
export const autonomyModeEnum = pgEnum('autonomy_mode', ['supervised', 'trusted', 'autonomous'])

export const agents = pgTable('agents', {
  id: uuid('id').primaryKey().defaultRandom(),
  roleId: uuid('role_id').notNull().references(() => roles.id),
  humanEmployeeId: uuid('human_employee_id').references(() => employees.id),
  status: agentStatusEnum('status').notNull().default('provisioning'),
  autonomyMode: autonomyModeEnum('autonomy_mode').notNull().default('supervised'),
  configJson: jsonb('config_json').default({}),   // openclaw.json snapshot
  podId: text('pod_id'),                           // Kubernetes pod name
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/skill.ts << 'EOF'
import { pgTable, uuid, text, timestamp, pgEnum } from 'drizzle-orm/pg-core'

export const trustLevelEnum = pgEnum('trust_level', ['verified', 'community', 'experimental'])
export const scanStatusEnum = pgEnum('scan_status', ['pending', 'passed', 'failed', 'manual_review'])

export const skills = pgTable('skills', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: text('name').notNull(),
  version: text('version').notNull(),
  category: text('category').notNull(),
  trustLevel: trustLevelEnum('trust_level').notNull().default('community'),
  clawHubRef: text('clawhub_ref'),                // upstream ClawHub skill ID
  scanStatus: scanStatusEnum('scan_status').notNull().default('pending'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/mcp-connection.ts << 'EOF'
import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core'
import { companies } from './company'

export const mcpConnections = pgTable('mcp_connections', {
  id: uuid('id').primaryKey().defaultRandom(),
  companyId: uuid('company_id').notNull().references(() => companies.id, { onDelete: 'cascade' }),
  name: text('name').notNull(),
  type: text('type').notNull(),                    // e.g. 'salesforce', 'jira', 'custom'
  serverUrl: text('server_url').notNull(),
  secretArn: text('secret_arn').notNull(),         // AWS Secrets Manager ARN
  allowedRoles: text('allowed_roles').array().default([]),
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/policy.ts << 'EOF'
import { pgTable, uuid, text, integer, timestamp, pgEnum } from 'drizzle-orm/pg-core'

export const policyScopeEnum = pgEnum('policy_scope', ['platform', 'company', 'department', 'agent'])

export const policies = pgTable('policies', {
  id: uuid('id').primaryKey().defaultRandom(),
  scope: policyScopeEnum('scope').notNull(),
  scopeId: uuid('scope_id'),                       // company/dept/agent id; null for platform
  regoRule: text('rego_rule').notNull(),
  priority: integer('priority').notNull().default(100),
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/audit-log.ts << 'EOF'
import { pgTable, uuid, text, jsonb, timestamp, numeric } from 'drizzle-orm/pg-core'
import { agents } from './agent'

export const auditLogs = pgTable('audit_logs', {
  id: uuid('id').primaryKey().defaultRandom(),
  agentId: uuid('agent_id').notNull().references(() => agents.id),
  actionType: text('action_type').notNull(),
  payload: jsonb('payload').default({}),
  result: text('result').notNull(),                // 'success' | 'blocked' | 'pending_approval'
  cost: numeric('cost', { precision: 10, scale: 6 }),
  timestamp: timestamp('timestamp').defaultNow().notNull(),
})
EOF

cat > packages/db/src/schema/approval-request.ts << 'EOF'
import { pgTable, uuid, text, timestamp, pgEnum } from 'drizzle-orm/pg-core'
import { agents } from './agent'
import { employees } from './employee'

export const approvalStatusEnum = pgEnum('approval_status', ['pending', 'approved', 'rejected', 'expired'])

export const approvalRequests = pgTable('approval_requests', {
  id: uuid('id').primaryKey().defaultRandom(),
  agentId: uuid('agent_id').notNull().references(() => agents.id),
  actionCategory: text('action_category').notNull(),
  actionDescription: text('action_description').notNull(),
  status: approvalStatusEnum('status').notNull().default('pending'),
  resolverId: uuid('resolver_id').references(() => employees.id),
  requestedAt: timestamp('requested_at').defaultNow().notNull(),
  resolvedAt: timestamp('resolved_at'),
  expiresAt: timestamp('expires_at').notNull(),
})
EOF

cat > packages/db/src/index.ts << 'EOF'
import { neon } from '@neondatabase/serverless'
import { drizzle } from 'drizzle-orm/neon-http'
import * as schema from './schema'

const sql = neon(process.env.DATABASE_URL!)

export const db = drizzle(sql, { schema })
export { schema }
export type DB = typeof db
EOF

cat > packages/db/drizzle.config.ts << 'EOF'
import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  schema: './src/schema/index.ts',
  out: './migrations',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
})
EOF

# packages/types
cat > packages/types/package.json << 'EOF'
{
  "name": "@staffstream/types",
  "version": "0.0.1",
  "exports": { ".": "./src/index.ts" }
}
EOF

mkdir -p packages/types/src
cat > packages/types/src/index.ts << 'EOF'
// Core domain types — shared across all apps

export type DataClassification = 'public' | 'internal' | 'confidential' | 'restricted'
export type AutonomyMode = 'supervised' | 'trusted' | 'autonomous'
export type AgentStatus = 'provisioning' | 'active' | 'paused' | 'terminated'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired'
export type MessageType = 'REQUEST' | 'RESPONSE' | 'BROADCAST' | 'ESCALATION' | 'SUPERVISION'
export type TrustLevel = 'verified' | 'community' | 'experimental'

export interface AgentMessage {
  id: string
  type: MessageType
  fromAgentId: string
  toAgentId: string
  payload: Record<string, unknown>
  dataClassification: DataClassification
  timestamp: string
}

export interface ApprovalGate {
  actionCategory: string
  agentId: string
  description: string
  estimatedCost?: number
  timeoutHours: number
}

export interface OpenClawConfig {
  agentId: string
  roleId: string
  companyId: string
  systemPrompt: string
  skills: string[]
  mcpConnections: MCPConnectionRef[]
  messageBusChannels: {
    inbound: string
    outbound: string
  }
  llm: {
    provider: 'anthropic' | 'openai'
    model: string
    maxTokens: number
    costLimitUsd: number
  }
}

export interface MCPConnectionRef {
  name: string
  serverUrl: string
  tokenEndpoint: string   // internal endpoint that issues scoped tokens
}
EOF

# packages/config
cat > packages/config/package.json << 'EOF'
{
  "name": "@staffstream/config",
  "version": "0.0.1",
  "exports": {
    "./eslint": "./eslint.js",
    "./tsconfig": "./tsconfig.base.json",
    "./tailwind": "./tailwind.config.js"
  }
}
EOF

cat > packages/config/tsconfig.base.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  }
}
EOF

# ── apps/web (Next.js) ─────────────────────────────────────────────────────────
mkdir -p apps/web/{app,components,lib,public}
mkdir -p apps/web/app/{api,\(admin\),\(employee\)}
mkdir -p apps/web/app/\(admin\)/{dashboard,departments,roles,employees,skills,settings}
mkdir -p apps/web/app/\(employee\)/{portal,approvals,kpis}
mkdir -p apps/web/app/api/{auth,admin,employee,agents,skills,approvals}
mkdir -p apps/web/components/{admin,employee,ui}
mkdir -p apps/web/lib/{db,auth,api}

cat > apps/web/package.json << 'EOF'
{
  "name": "@staffstream/web",
  "version": "0.0.1",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@auth0/nextjs-auth0": "^3.5.0",
    "@staffstream/db": "workspace:*",
    "@staffstream/types": "workspace:*",
    "zod": "^3.23.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0"
  },
  "devDependencies": {
    "@staffstream/config": "workspace:*",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0"
  }
}
EOF

cat > apps/web/next.config.ts << 'EOF'
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  transpilePackages: ['@staffstream/db', '@staffstream/types'],
}

export default nextConfig
EOF

cat > apps/web/app/layout.tsx << 'EOF'
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'StaffStream',
  description: 'An AI assistant for every employee.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
EOF

cat > apps/web/app/globals.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --cream: #F5EEDC;
  --navy: #183B4E;
  --blue: #27548A;
  --gold: #DDA853;
}
EOF

cat > apps/web/app/page.tsx << 'EOF'
// Landing / redirect page
// Unauthenticated users → /auth/login
// Admin users → /dashboard
// Employee users → /portal
import { redirect } from 'next/navigation'

export default function Home() {
  redirect('/api/auth/login')
}
EOF

# API route stubs
cat > apps/web/app/api/auth/\[auth0\]/route.ts << 'EOF'
import { handleAuth } from '@auth0/nextjs-auth0'
export const GET = handleAuth()
EOF

cat > apps/web/app/api/admin/companies/route.ts << 'EOF'
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

const CreateCompanySchema = z.object({
  name: z.string().min(2).max(100),
})

export async function POST(req: NextRequest) {
  // TODO: authenticate request (Auth0 JWT)
  // TODO: create company record + generate unique code
  // TODO: return { id, code }
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}

export async function GET(req: NextRequest) {
  // TODO: return company details for authenticated admin
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}
EOF

cat > apps/web/app/api/admin/departments/route.ts << 'EOF'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(req: NextRequest) {
  // TODO: list departments for company
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}

export async function POST(req: NextRequest) {
  // TODO: create department
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}
EOF

cat > apps/web/app/api/agents/provision/route.ts << 'EOF'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  // TODO: validate admin auth
  // TODO: call provision-agent script
  // Triggers: scripts/provision-agent.ts
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}
EOF

cat > apps/web/app/api/approvals/route.ts << 'EOF'
import { NextRequest, NextResponse } from 'next/server'

export async function GET(req: NextRequest) {
  // TODO: return pending approvals for authenticated employee
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}

export async function PATCH(req: NextRequest) {
  // TODO: approve or reject an approval request
  // Body: { id, action: 'approve' | 'reject' }
  return NextResponse.json({ message: 'Not implemented yet' }, { status: 501 })
}
EOF

# Admin UI stubs
cat > apps/web/app/\(admin\)/dashboard/page.tsx << 'EOF'
// Admin dashboard — company overview, adoption stats
export default function AdminDashboard() {
  return (
    <main>
      <h1>StaffStream Admin</h1>
      <p>TODO: org overview, department stats, recent activity</p>
    </main>
  )
}
EOF

cat > apps/web/app/\(admin\)/departments/page.tsx << 'EOF'
// Department management — list, create, edit departments
export default function DepartmentsPage() {
  return (
    <main>
      <h1>Departments</h1>
      <p>TODO: department list + create form</p>
    </main>
  )
}
EOF

# Employee portal stub
cat > apps/web/app/\(employee\)/portal/page.tsx << 'EOF'
// Employee portal — chat with AI assistant
export default function EmployeePortal() {
  return (
    <main>
      <h1>Welcome to StaffStream</h1>
      <p>TODO: AI assistant avatar + chat interface (WebSocket)</p>
    </main>
  )
}
EOF

cat > apps/web/app/\(employee\)/approvals/page.tsx << 'EOF'
// Approval queue — employee reviews and approves/rejects agent actions
export default function ApprovalsPage() {
  return (
    <main>
      <h1>Approval Queue</h1>
      <p>TODO: list pending approvals with approve/reject actions</p>
    </main>
  )
}
EOF

# ── apps/governance ────────────────────────────────────────────────────────────
mkdir -p apps/governance/{policy-engine,message-bus,hierarchy-enforcer}
mkdir -p apps/governance/policy-engine/{policies,src}
mkdir -p apps/governance/message-bus/src
mkdir -p apps/governance/hierarchy-enforcer/src

cat > apps/governance/package.json << 'EOF'
{
  "name": "@staffstream/governance",
  "version": "0.0.1",
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@staffstream/db": "workspace:*",
    "@staffstream/types": "workspace:*",
    "ioredis": "^5.3.0",
    "node-opa-wasm": "^1.8.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.4.0"
  }
}
EOF

cat > apps/governance/message-bus/src/router.ts << 'EOF'
/**
 * Message Bus Router
 * Receives inter-agent messages on the outbound stream,
 * runs them through the policy engine, then delivers
 * to the recipient's inbound stream.
 *
 * All inter-agent communication MUST route through here.
 * Agents never communicate directly.
 */

// TODO: implement Redis Streams consumer group
// TODO: integrate OPA policy evaluation
// TODO: data classification check on payload
// TODO: route to recipient inbound stream
// TODO: write to AuditLog on every message (pass or block)
// TODO: dead letter queue for blocked messages

export {}
EOF

cat > apps/governance/policy-engine/policies/platform.rego << 'EOF'
# Platform-level policies — NEVER override these
package staffstream.platform

# Block any action that exceeds the company cost threshold
# without prior human approval
deny[msg] {
  input.action.estimatedCostUsd > input.company.costThresholdUsd
  not input.action.hasApproval
  msg := "Action exceeds cost threshold — human approval required"
}

# Block cross-department messages involving Restricted data
deny[msg] {
  input.message.dataClassification == "restricted"
  input.sender.departmentId != input.recipient.departmentId
  msg := "Restricted data cannot cross department boundaries"
}
EOF

cat > apps/governance/policy-engine/policies/default-company.rego << 'EOF'
# Default company-level policy template
# Admins can extend/override these per company
package staffstream.company

# First-time cross-department communication requires approval
deny[msg] {
  input.message.type == "REQUEST"
  input.sender.departmentId != input.recipient.departmentId
  not input.action.hasApproval
  not data.approved_pairs[sprintf("%v:%v", [input.sender.departmentId, input.recipient.departmentId])]
  msg := "First cross-department contact requires human approval"
}
EOF

cat > apps/governance/hierarchy-enforcer/src/enforcer.ts << 'EOF'
/**
 * Hierarchy Enforcer
 * Background daemon that:
 * - Polls subordinate agent Lobster workflow states
 * - Aggregates KPI progress for manager agents
 * - Handles escalations when subordinate agents hit blockers
 * - Monitors per-agent cost and alerts on threshold breach
 *
 * Runs on a configurable interval (default: every 5 minutes)
 */

// TODO: query Lobster workflow states per agent
// TODO: build KPI aggregation report for manager agent
// TODO: detect stuck workflows and trigger ESCALATION messages
// TODO: monitor cumulative cost per agent vs budget
// TODO: push supervision summaries to manager agent inbound stream

export {}
EOF

# ── scripts ────────────────────────────────────────────────────────────────────
mkdir -p scripts

cat > scripts/provision-agent.ts << 'EOF'
/**
 * Agent Provisioner
 * Called when an admin assigns a virtual employee slot to a human employee.
 *
 * Steps:
 * 1. Load role config (skills, MCP connections) from DB
 * 2. Generate openclaw.json config
 * 3. Create Kubernetes pod in tenant namespace
 * 4. Install curated skills via clawhub install
 * 5. Configure MCP connections via MCPorter (scoped tokens from Secrets Manager)
 * 6. Register agent with Message Bus and Hierarchy Enforcer
 * 7. Send invitation email to human employee
 *
 * Usage:
 *   pnpm tsx scripts/provision-agent.ts --role-id=<uuid> --employee-id=<uuid>
 */

import { parseArgs } from 'node:util'

const { values } = parseArgs({
  args: process.argv.slice(2),
  options: {
    'role-id': { type: 'string' },
    'employee-id': { type: 'string' },
  },
})

const roleId = values['role-id']
const employeeId = values['employee-id']

if (!roleId || !employeeId) {
  console.error('Usage: pnpm tsx scripts/provision-agent.ts --role-id=<uuid> --employee-id=<uuid>')
  process.exit(1)
}

async function provisionAgent() {
  console.log(`Provisioning agent for role=${roleId}, employee=${employeeId}`)

  // TODO: Step 1 — load role from DB
  // TODO: Step 2 — generate openclaw.json
  // TODO: Step 3 — kubectl apply pod manifest in tenant namespace
  // TODO: Step 4 — clawhub install (curated skills only)
  // TODO: Step 5 — MCPorter config with Secrets Manager tokens
  // TODO: Step 6 — register with message bus
  // TODO: Step 7 — send invitation email via SES

  console.log('Agent provisioned successfully (TODO: implement)')
}

provisionAgent().catch(console.error)
EOF

cat > scripts/seed-db.ts << 'EOF'
/**
 * Development database seeder
 * Creates a sample org: Litmus Automations
 * - 2 departments: Sales, Engineering
 * - 3 roles: Sales Rep, Sales Manager, Engineer
 * - Reporting lines: Sales Rep → Sales Manager
 * - 5 sample skills pre-loaded
 */

import { db, schema } from '@staffstream/db'

async function seed() {
  console.log('🌱 Seeding database...')

  // TODO: insert sample company
  // TODO: insert departments
  // TODO: insert roles with reporting lines
  // TODO: insert sample skills (curated, scan_status='passed')
  // TODO: insert a sample employee and agent for development

  console.log('✅ Seed complete')
}

seed().catch(console.error)
EOF

# ── docs ───────────────────────────────────────────────────────────────────────
mkdir -p docs

cat > docs/data-model.md << 'EOF'
# StaffStream Data Model

See `packages/db/src/schema/` for the canonical Drizzle schema definitions.

## Entity relationships

Company → Departments → Roles → Agents (one per Employee)
Employee (human) → Agent (AI counterpart)
Skill (many-to-many with Roles via default_skills[])
MCPConnection (scoped to Company, allowed for specific Roles)
Policy (platform / company / department / agent scope)
AuditLog (append-only log of every agent action)
ApprovalRequest (HITL gate — agents pause and wait for human resolution)

## Multi-tenancy

All tables include `company_id`. Row-level security is enforced in Postgres:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <table>
  USING (company_id = current_setting('app.company_id')::uuid);
```

Set `app.company_id` at the start of every DB session in middleware.
EOF

cat > docs/api.md << 'EOF'
# StaffStream API Reference

Base URL: `/api`

## Authentication

All endpoints require a valid Auth0 JWT in the `Authorization: Bearer <token>` header.
Middleware extracts `company_id` from the JWT and sets it on the DB session.

## Admin endpoints (require admin role)

POST   /admin/companies              — register a new company
GET    /admin/companies/:id          — get company details
POST   /admin/departments            — create department
GET    /admin/departments            — list departments
POST   /admin/roles                  — create role
POST   /admin/employees              — invite human employee
POST   /agents/provision             — provision OpenClaw agent for an employee

## Employee endpoints (require authenticated employee)

GET    /employee/agent               — get own agent status and config
POST   /employee/agent/kpis          — set KPIs for own agent
GET    /approvals                    — list pending approvals
PATCH  /approvals/:id                — approve or reject an action

## Shared

GET    /skills                       — browse curated skill marketplace
GET    /skills/:id                   — skill details
EOF

# Final CLAUDE.md copy into root
cp "$(dirname "$0")/CLAUDE.md" . 2>/dev/null || echo "# Copy CLAUDE.md into this directory from the outputs folder"

echo ""
echo "✅ StaffStream scaffold complete!"
echo ""
echo "Next steps:"
echo "  1. cd staffstream"
echo "  2. cp .env.example .env.local  # fill in your values"
echo "  3. pnpm install"
echo "  4. pnpm db:migrate             # initialise Neon database"
echo "  5. pnpm dev                    # start Next.js dev server"
echo ""
echo "Then open Claude Code in this directory:"
echo "  claude                         # starts Claude Code CLI"
echo ""
echo "Phase 1 build order (see CLAUDE.md for full scope):"
echo "  1. Auth0 integration (apps/web/lib/auth/)"
echo "  2. Admin company registration API + UI"
echo "  3. Department + role creation"
echo "  4. Agent provisioner script (scripts/provision-agent.ts)"
echo "  5. Employee portal chat UI (WebSocket to OpenClaw)"
echo "  6. Approval queue (HITL gate)"
EOF

chmod +x /mnt/user-data/outputs/scaffold.sh
