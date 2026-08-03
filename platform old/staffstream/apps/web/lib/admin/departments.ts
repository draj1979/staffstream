import { schema, type TenantTx } from '@staffstream/db'
import { and, eq } from 'drizzle-orm'
import { z } from 'zod'

export const createDepartmentSchema = z.object({
  name: z.string().min(2),
  dataClassification: z.enum(['public', 'internal', 'confidential', 'restricted']).optional(),
})
export type CreateDepartmentInput = z.infer<typeof createDepartmentSchema>

export async function createDepartment(tx: TenantTx, companyId: string, input: CreateDepartmentInput) {
  const rows = await tx
    .insert(schema.departments)
    .values({
      companyId,
      name: input.name,
      ...(input.dataClassification ? { dataClassification: input.dataClassification } : {}),
    })
    .returning()

  const department = rows[0]
  if (!department) {
    throw new Error('Insert returned no row')
  }
  return department
}

/**
 * Department + its roles, scoped to `companyId` at the SQL level (unlike the
 * company GET, which has to compare against the session after the fact —
 * departments actually carry a company_id column to filter on).
 * Returns null if the department doesn't exist or belongs to another company.
 */
export async function getDepartmentWithRoles(tx: TenantTx, companyId: string, departmentId: string) {
  const rows = await tx
    .select({ department: schema.departments, role: schema.roles })
    .from(schema.departments)
    .leftJoin(schema.roles, eq(schema.roles.departmentId, schema.departments.id))
    .where(and(eq(schema.departments.id, departmentId), eq(schema.departments.companyId, companyId)))

  const first = rows[0]
  if (!first) return null

  return {
    ...first.department,
    roles: rows.map((r) => r.role).filter((r): r is NonNullable<typeof r> => r !== null),
  }
}
