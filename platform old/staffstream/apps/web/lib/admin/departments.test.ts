import { db, schema, withTenantContext } from '@staffstream/db'
import { eq } from 'drizzle-orm'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { generateCompanyCode } from '../codes'
import { createDepartment, createDepartmentSchema, getDepartmentWithRoles } from './departments'

// Runs against the real Neon dev DB (see route.integration.test.ts under
// app/api/admin/companies for why: no separate test DB/branch exists yet).
// Tenant auth (Auth0 session) can't be faked outside a real request context,
// so these test the lib/admin business logic directly with a real
// withTenantContext transaction, skipping the HTTP + getCurrentUser layer —
// the route handlers themselves are thin wrappers around these functions.
//
// Cleanup only deletes the companies created here: department -> company and
// role -> department are both ON DELETE CASCADE, so that's sufficient.

let companyId: string
const otherCompanyIds: string[] = []

describe('departments (integration)', () => {
  beforeAll(async () => {
    const rows = await db
      .insert(schema.companies)
      .values({ name: 'Departments Test Co', code: generateCompanyCode() })
      .returning()
    companyId = rows[0]!.id
  })

  afterAll(async () => {
    await db.delete(schema.companies).where(eq(schema.companies.id, companyId))
    for (const id of otherCompanyIds) {
      await db.delete(schema.companies).where(eq(schema.companies.id, id))
    }
  })

  it('creates a department scoped to the company, defaulting dataClassification', async () => {
    const department = await withTenantContext(companyId, (tx) =>
      createDepartment(tx, companyId, { name: 'Engineering' })
    )

    expect(department.name).toBe('Engineering')
    expect(department.companyId).toBe(companyId)
    expect(department.dataClassification).toBe('internal')
  })

  it('accepts an explicit dataClassification', async () => {
    const department = await withTenantContext(companyId, (tx) =>
      createDepartment(tx, companyId, { name: 'Finance', dataClassification: 'confidential' })
    )
    expect(department.dataClassification).toBe('confidential')
  })

  it('rejects a name shorter than 2 characters', () => {
    const parsed = createDepartmentSchema.safeParse({ name: 'A' })
    expect(parsed.success).toBe(false)
  })

  it('GET returns the department with its roles joined (empty for now)', async () => {
    const department = await withTenantContext(companyId, (tx) =>
      createDepartment(tx, companyId, { name: 'Sales' })
    )

    const result = await withTenantContext(companyId, (tx) =>
      getDepartmentWithRoles(tx, companyId, department.id)
    )

    expect(result).not.toBeNull()
    expect(result!.name).toBe('Sales')
    expect(result!.roles).toEqual([])
  })

  it('returns null for a department that belongs to a different company', async () => {
    const otherRows = await db
      .insert(schema.companies)
      .values({ name: 'Other Co', code: generateCompanyCode() })
      .returning()
    const otherCompanyId = otherRows[0]!.id
    otherCompanyIds.push(otherCompanyId)

    const department = await withTenantContext(companyId, (tx) =>
      createDepartment(tx, companyId, { name: 'Isolated Dept' })
    )

    const result = await withTenantContext(otherCompanyId, (tx) =>
      getDepartmentWithRoles(tx, otherCompanyId, department.id)
    )
    expect(result).toBeNull()
  })

  it('returns null for a department id that does not exist', async () => {
    const result = await withTenantContext(companyId, (tx) =>
      getDepartmentWithRoles(tx, companyId, '00000000-0000-0000-0000-000000000000')
    )
    expect(result).toBeNull()
  })
})
