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
