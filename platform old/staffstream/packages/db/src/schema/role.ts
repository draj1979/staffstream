import { sql } from 'drizzle-orm'
import { pgTable, uuid, text, integer, timestamp, type AnyPgColumn } from 'drizzle-orm/pg-core'
import { departments } from './department'

export const roles = pgTable('roles', {
  id: uuid('id').primaryKey().defaultRandom(),
  departmentId: uuid('department_id').notNull().references(() => departments.id, { onDelete: 'cascade' }),
  name: text('name').notNull(),
  seniorityLevel: integer('seniority_level').notNull().default(1),
  reportsToRoleId: uuid('reports_to_role_id').references((): AnyPgColumn => roles.id),
  defaultSkills: text('default_skills').array().default(sql`'{}'::text[]`),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})
