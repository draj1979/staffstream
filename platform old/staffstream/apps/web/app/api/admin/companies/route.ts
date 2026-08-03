import { db, schema } from '@staffstream/db'
import { NextResponse, type NextRequest } from 'next/server'
import { z } from 'zod'
import { generateCompanyCode } from '@/lib/codes'

const createCompanySchema = z.object({
  name: z.string().min(2),
})

const MAX_CODE_ATTEMPTS = 5
const UNIQUE_VIOLATION = '23505'

async function insertCompanyWithUniqueCode(name: string) {
  for (let attempt = 0; attempt < MAX_CODE_ATTEMPTS; attempt++) {
    const code = generateCompanyCode()
    try {
      const rows = await db.insert(schema.companies).values({ name, code }).returning()
      const company = rows[0]
      if (!company) {
        throw new Error('Insert returned no row')
      }
      return company
    } catch (err) {
      // A code collision only ever shows up on the `code` unique constraint —
      // anything else (bad connection, NOT NULL violation, etc) should bubble up.
      if ((err as { code?: string }).code === UNIQUE_VIOLATION) {
        continue
      }
      throw err
    }
  }
  throw new Error(`Could not generate a unique company code after ${MAX_CODE_ATTEMPTS} attempts`)
}

// No auth guard: creating a company is the bootstrap step before any
// company-scoped Auth0 session (or company_id claim) can exist, so it can't
// sit behind the tenant-scoped middleware the way GET /:id does. This is
// fine for local/dev use but must be locked down (e.g. a platform-admin
// secret header, or restricting it to an internal network) before this is
// reachable from the public internet.
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null)
  const parsed = createCompanySchema.safeParse(body)

  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_input', issues: parsed.error.issues }, { status: 400 })
  }

  const company = await insertCompanyWithUniqueCode(parsed.data.name)

  return NextResponse.json(
    { id: company.id, name: company.name, code: company.code },
    { status: 201 }
  )
}
