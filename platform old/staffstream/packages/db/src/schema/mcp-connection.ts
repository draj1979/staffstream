import { sql } from 'drizzle-orm'
import { pgTable, uuid, text, timestamp } from 'drizzle-orm/pg-core'
import { companies } from './company'

export const mcpConnections = pgTable('mcp_connections', {
  id: uuid('id').primaryKey().defaultRandom(),
  companyId: uuid('company_id').notNull().references(() => companies.id, { onDelete: 'cascade' }),
  name: text('name').notNull(),
  type: text('type').notNull(),                    // e.g. 'salesforce', 'jira', 'custom'
  serverUrl: text('server_url').notNull(),
  secretArn: text('secret_arn').notNull(),         // AWS Secrets Manager ARN
  allowedRoles: text('allowed_roles').array().default(sql`'{}'::text[]`),
  createdAt: timestamp('created_at').defaultNow().notNull(),
})
