import { NextResponse, type NextRequest } from 'next/server'
import { UnauthenticatedError, withCurrentUserDb } from '@/lib/auth/session'
import { createDepartment, createDepartmentSchema } from '@/lib/admin/departments'

// Protected by middleware.ts — unlike companies, a department can never
// exist without a company, so both POST and GET here require a session.
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null)
  const parsed = createDepartmentSchema.safeParse(body)

  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_input', issues: parsed.error.issues }, { status: 400 })
  }

  try {
    const department = await withCurrentUserDb((tx, user) => createDepartment(tx, user.companyId, parsed.data))
    return NextResponse.json(department, { status: 201 })
  } catch (err) {
    if (err instanceof UnauthenticatedError) {
      return NextResponse.json({ error: 'not_authenticated' }, { status: 401 })
    }
    throw err
  }
}
