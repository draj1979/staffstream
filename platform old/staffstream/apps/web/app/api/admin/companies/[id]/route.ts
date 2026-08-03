import { schema } from '@staffstream/db'
import { eq } from 'drizzle-orm'
import { NextResponse } from 'next/server'
import { UnauthenticatedError, withCurrentUserDb } from '@/lib/auth/session'

// Protected by middleware.ts (matcher includes /api/admin/companies/:path+).
// Scoped so a company admin can only ever read their own company, regardless
// of what :id is requested — there's no company-level RLS policy yet (see
// packages/db), so this check is the only thing enforcing that boundary.
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const rows = await withCurrentUserDb(async (tx, user) => {
      if (user.companyId !== params.id) {
        return null
      }
      return tx
        .select({ company: schema.companies, department: schema.departments })
        .from(schema.companies)
        .leftJoin(schema.departments, eq(schema.departments.companyId, schema.companies.id))
        .where(eq(schema.companies.id, params.id))
    })

    const firstRow = rows?.[0]
    if (!firstRow) {
      return NextResponse.json({ error: 'not_found' }, { status: 404 })
    }

    const { id, name, code, subscriptionTier, settingsJson, createdAt, updatedAt } = firstRow.company
    const departments = rows.map((r) => r.department).filter((d) => d !== null)

    return NextResponse.json({
      id,
      name,
      code,
      subscriptionTier,
      settingsJson,
      createdAt,
      updatedAt,
      departments,
    })
  } catch (err) {
    if (err instanceof UnauthenticatedError) {
      return NextResponse.json({ error: 'not_authenticated' }, { status: 401 })
    }
    throw err
  }
}
