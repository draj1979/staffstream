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
