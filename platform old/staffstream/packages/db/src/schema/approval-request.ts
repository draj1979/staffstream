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
