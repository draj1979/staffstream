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
