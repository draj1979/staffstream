import { db, schema, withTenantContext } from '@staffstream/db'
import { eq } from 'drizzle-orm'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { generateCompanyCode } from '../codes'
import { InvalidReferenceError } from './errors'
import { createRole, createRoleSchema, getRoleWithAgents } from './roles'

// See departments.test.ts for why this hits the real dev DB directly via
// withTenantContext rather than going through Auth0 + the HTTP route.

let companyId: string
let departmentId: string
const otherCompanyIds: string[] = []

describe('roles (integration)', () => {
  beforeAll(async () => {
    const companyRows = await db
      .insert(schema.companies)
      .values({ name: 'Roles Test Co', code: generateCompanyCode() })
      .returning()
    companyId = companyRows[0]!.id

    const departmentRows = await db
      .insert(schema.departments)
      .values({ companyId, name: 'Roles Test Dept' })
      .returning()
    departmentId = departmentRows[0]!.id
  })

  afterAll(async () => {
    // department/role rows cascade from their company's deletion.
    await db.delete(schema.companies).where(eq(schema.companies.id, companyId))
    for (const id of otherCompanyIds) {
      await db.delete(schema.companies).where(eq(schema.companies.id, id))
    }
  })

  it('rejects a name shorter than 2 characters', () => {
    const parsed = createRoleSchema.safeParse({ name: 'A', departmentId })
    expect(parsed.success).toBe(false)
  })

  it('rejects a non-uuid departmentId', () => {
    const parsed = createRoleSchema.safeParse({ name: 'Valid Name', departmentId: 'not-a-uuid' })
    expect(parsed.success).toBe(false)
  })

  it('creates a role under a department in the same company, defaulting seniorityLevel', async () => {
    const role = await withTenantContext(companyId, (tx) =>
      createRole(tx, companyId, { name: 'Software Engineer', departmentId })
    )

    expect(role.name).toBe('Software Engineer')
    expect(role.departmentId).toBe(departmentId)
    expect(role.seniorityLevel).toBe(1)
    expect(role.defaultSkills).toEqual([])
  })

  it('rejects a departmentId that belongs to another company', async () => {
    const otherCompanyRows = await db
      .insert(schema.companies)
      .values({ name: 'Other Roles Co', code: generateCompanyCode() })
      .returning()
    const otherCompanyId = otherCompanyRows[0]!.id
    otherCompanyIds.push(otherCompanyId)

    const otherDepartmentRows = await db
      .insert(schema.departments)
      .values({ companyId: otherCompanyId, name: 'Other Dept' })
      .returning()

    await expect(
      withTenantContext(companyId, (tx) =>
        createRole(tx, companyId, { name: 'Intruder', departmentId: otherDepartmentRows[0]!.id })
      )
    ).rejects.toThrow(InvalidReferenceError)
  })

  it('accepts a reportsToRoleId within the same company', async () => {
    const manager = await withTenantContext(companyId, (tx) =>
      createRole(tx, companyId, { name: 'Engineering Manager', departmentId })
    )

    const report = await withTenantContext(companyId, (tx) =>
      createRole(tx, companyId, {
        name: 'Junior Engineer',
        departmentId,
        reportsToRoleId: manager.id,
      })
    )

    expect(report.reportsToRoleId).toBe(manager.id)
  })

  it('rejects a reportsToRoleId that belongs to another company', async () => {
    const otherCompanyRows = await db
      .insert(schema.companies)
      .values({ name: 'Other Roles Co 2', code: generateCompanyCode() })
      .returning()
    const otherCompanyId = otherCompanyRows[0]!.id
    otherCompanyIds.push(otherCompanyId)

    const otherDepartmentRows = await db
      .insert(schema.departments)
      .values({ companyId: otherCompanyId, name: 'Other Dept 2' })
      .returning()
    const otherRoleRows = await db
      .insert(schema.roles)
      .values({ departmentId: otherDepartmentRows[0]!.id, name: 'Foreign Role' })
      .returning()

    await expect(
      withTenantContext(companyId, (tx) =>
        createRole(tx, companyId, {
          name: 'Should Fail',
          departmentId,
          reportsToRoleId: otherRoleRows[0]!.id,
        })
      )
    ).rejects.toThrow(InvalidReferenceError)
  })

  it('GET returns the role with its assigned agents joined (empty for now)', async () => {
    const role = await withTenantContext(companyId, (tx) =>
      createRole(tx, companyId, { name: 'Support Engineer', departmentId })
    )

    const result = await withTenantContext(companyId, (tx) => getRoleWithAgents(tx, companyId, role.id))
    expect(result).not.toBeNull()
    expect(result!.name).toBe('Support Engineer')
    expect(result!.agents).toEqual([])
  })

  it('returns null for a role that belongs to a different company', async () => {
    const role = await withTenantContext(companyId, (tx) =>
      createRole(tx, companyId, { name: 'Scoped Role', departmentId })
    )

    const otherCompanyRows = await db
      .insert(schema.companies)
      .values({ name: 'Other Roles Co 3', code: generateCompanyCode() })
      .returning()
    const otherCompanyId = otherCompanyRows[0]!.id
    otherCompanyIds.push(otherCompanyId)

    const result = await withTenantContext(otherCompanyId, (tx) => getRoleWithAgents(tx, otherCompanyId, role.id))
    expect(result).toBeNull()
  })
})
