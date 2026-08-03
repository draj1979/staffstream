import { NextResponse, type NextRequest } from 'next/server'
import { UnauthenticatedError, withCurrentUserDb } from '@/lib/auth/session'
import { InvalidReferenceError } from '@/lib/admin/errors'
import { createRole, createRoleSchema } from '@/lib/admin/roles'

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null)
  const parsed = createRoleSchema.safeParse(body)

  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_input', issues: parsed.error.issues }, { status: 400 })
  }

  try {
    const role = await withCurrentUserDb((tx, user) => createRole(tx, user.companyId, parsed.data))
    return NextResponse.json(role, { status: 201 })
  } catch (err) {
    if (err instanceof UnauthenticatedError) {
      return NextResponse.json({ error: 'not_authenticated' }, { status: 401 })
    }
    if (err instanceof InvalidReferenceError) {
      return NextResponse.json({ error: 'invalid_reference', description: err.message }, { status: 400 })
    }
    throw err
  }
}
