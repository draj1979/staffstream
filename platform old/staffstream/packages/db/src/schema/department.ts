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
