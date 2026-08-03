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
