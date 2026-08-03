import { NextResponse } from 'next/server'
import { UnauthenticatedError, withCurrentUserDb } from '@/lib/auth/session'
import { getDepartmentWithRoles } from '@/lib/admin/departments'

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const department = await withCurrentUserDb((tx, user) =>
      getDepartmentWithRoles(tx, user.companyId, params.id)
    )

    if (!department) {
      return NextResponse.json({ error: 'not_found' }, { status: 404 })
    }
    return NextResponse.json(department)
  } catch (err) {
    if (err instanceof UnauthenticatedError) {
      return NextResponse.json({ error: 'not_authenticated' }, { status: 401 })
    }
    throw err
  }
}
