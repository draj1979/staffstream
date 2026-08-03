import { NextResponse } from 'next/server'
import { UnauthenticatedError, withCurrentUserDb } from '@/lib/auth/session'
import { getRoleWithAgents } from '@/lib/admin/roles'

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const role = await withCurrentUserDb((tx, user) => getRoleWithAgents(tx, user.companyId, params.id))

    if (!role) {
      return NextResponse.json({ error: 'not_found' }, { status: 404 })
    }
    return NextResponse.json(role)
  } catch (err) {
    if (err instanceof UnauthenticatedError) {
      return NextResponse.json({ error: 'not_authenticated' }, { status: 401 })
    }
    throw err
  }
}
