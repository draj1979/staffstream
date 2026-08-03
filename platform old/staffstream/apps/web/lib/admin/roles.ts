import { schema, type TenantTx } from '@staffstream/db'
import { and, eq } from 'drizzle-orm'
import { z } from 'zod'
import { InvalidReferenceError } from './errors'

export const createRoleSchema = z.object({
  name: z.string().min(2),
  departmentId: z.string().uuid(),
  seniorityLevel: z.number().int().min(1).optional(),
  reportsToRoleId: z.string().uuid().optional(),
  defaultSkills: z.array(z.string()).optional(),
})
export type CreateRoleInput = z.infer<typeof createRoleSchema>

export async function createRole(tx: TenantTx, companyId: string, input: CreateRoleInput) {
  const [department] = await tx
    .select({ id: schema.departments.id })
    .from(schema.departments)
    .where(and(eq(schema.departments.id, input.departmentId), eq(schema.departments.companyId, companyId)))

  if (!department) {
    throw new InvalidReferenceError(`departmentId "${input.departmentId}" not found in this company`)
  }

  if (input.reportsToRoleId) {
    const [reportsTo] = await tx
      .select({ id: schema.roles.id })
      .from(schema.roles)
      .innerJoin(schema.departments, eq(schema.departments.id, schema.roles.departmentId))
      .where(and(eq(schema.roles.id, input.reportsToRoleId), eq(schema.departments.companyId, companyId)))

    if (!reportsTo) {
      throw new InvalidReferenceError(`reportsToRoleId "${input.reportsToRoleId}" not found in this company`)
    }
  }

  const rows = await tx
    .insert(schema.roles)
    .values({
      departmentId: input.departmentId,
      name: input.name,
      ...(input.seniorityLevel !== undefined ? { seniorityLevel: input.seniorityLevel } : {}),
      ...(input.reportsToRoleId !== undefined ? { reportsToRoleId: input.reportsToRoleId } : {}),
      ...(input.defaultSkills !== undefined ? { defaultSkills: input.defaultSkills } : {}),
    })
    .returning()

  const role = rows[0]
  if (!role) {
    throw new Error('Insert returned no row')
  }
  return role
}

/**
 * Role + the agents currently assigned to it, scoped to `companyId` through
 * the role's department (roles have no company_id column of their own).
 * Returns null if the role doesn't exist or belongs to another company.
 */
export async function getRoleWithAgents(tx: TenantTx, companyId: string, roleId: string) {
  const rows = await tx
    .select({ role: schema.roles, agent: schema.agents })
    .from(schema.roles)
    .innerJoin(schema.departments, eq(schema.departments.id, schema.roles.departmentId))
    .leftJoin(schema.agents, eq(schema.agents.roleId, schema.roles.id))
    .where(and(eq(schema.roles.id, roleId), eq(schema.departments.companyId, companyId)))

  const first = rows[0]
  if (!first) return null

  return {
    ...first.role,
    agents: rows.map((r) => r.agent).filter((a): a is NonNullable<typeof a> => a !== null),
  }
}
