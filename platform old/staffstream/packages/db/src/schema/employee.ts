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
