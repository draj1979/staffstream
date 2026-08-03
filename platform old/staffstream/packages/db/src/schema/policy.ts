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
