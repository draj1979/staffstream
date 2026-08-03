import { NextResponse } from 'next/server'
import { getCurrentUser } from '@/lib/auth/session'

export async function GET() {
  let user
  try {
    user = await getCurrentUser()
  } catch (err) {
    return NextResponse.json(
      { error: 'misconfigured_account', description: (err as Error).message },
      { status: 403 }
    )
  }

  if (!user) {
    return NextResponse.json({ error: 'not_authenticated' }, { status: 401 })
  }
  return NextResponse.json({ role: user.role })
}
