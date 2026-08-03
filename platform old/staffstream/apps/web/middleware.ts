import { getSession, withMiddlewareAuthRequired } from '@auth0/nextjs-auth0/edge'
import { NextResponse, type NextRequest } from 'next/server'
import { AUTH0_COMPANY_ID_CLAIM, AUTH0_ROLE_CLAIM, HEADER_COMPANY_ID, HEADER_USER_ROLE } from './lib/auth/claims'

// withMiddlewareAuthRequired already redirects unauthenticated page requests
// to /api/auth/login (with a returnTo back to the original URL) and returns a
// 401 for unauthenticated /api requests. We only need to add the tenant
// extraction on top of that.
export default withMiddlewareAuthRequired(async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getSession(req, res)
  const companyId = session?.user?.[AUTH0_COMPANY_ID_CLAIM]

  if (!companyId || typeof companyId !== 'string') {
    // Authenticated, but the account isn't wired up with a company yet.
    // Don't send them back through /api/auth/login — they'd just bounce
    // right back here in a loop.
    return NextResponse.json(
      { error: 'no_company', description: 'This account has no company_id claim.' },
      { status: 403 }
    )
  }

  // Middleware can't hand a DB session variable to a later Route Handler
  // invocation (separate request lifecycle, and the neon-http driver has no
  // persistent session anyway) — see packages/db/src/tenant.ts. Instead we
  // forward the tenant identity downstream via headers; each Route Handler
  // opens its own withTenantContext(companyId, ...) transaction per query.
  res.headers.set(HEADER_COMPANY_ID, companyId)
  const role = session?.user?.[AUTH0_ROLE_CLAIM]
  if (typeof role === 'string') {
    res.headers.set(HEADER_USER_ROLE, role)
  }

  return res
})

export const config = {
  // /admin/* and /employee/* as requested, plus the routes that actually
  // exist today. app/(admin) and app/(employee) are Next.js route GROUPS —
  // the parens are stripped from the URL, so pages under them are served at
  // /dashboard, /portal, etc, not /admin/dashboard or /employee/portal. If
  // those folders get moved under real app/admin/ and app/employee/
  // segments later, this list can collapse back down to the two wildcards.
  matcher: [
    '/admin/:path*',
    '/employee/:path*',
    // Deliberately NOT '/api/admin/:path*': POST /api/admin/companies is the
    // tenant-bootstrap endpoint (creates the company itself), so it can't
    // require a company-scoped session — there's no company yet. Everything
    // *under* a created company (companies/:id, and future admin
    // sub-resources) should still be listed here explicitly.
    '/api/admin/companies/:path+',
    // Departments and roles can't exist without a company already having
    // been created, so — unlike companies — both the collection (POST) and
    // item (GET) routes require a session; no bootstrap exemption needed.
    '/api/admin/departments/:path*',
    '/api/admin/roles/:path*',
    '/api/employee/:path*',
    '/dashboard/:path*',
    '/departments/:path*',
    '/employees/:path*',
    '/roles/:path*',
    '/settings/:path*',
    '/skills/:path*',
    '/approvals/:path*',
    '/kpis/:path*',
    '/portal/:path*',
  ],
}
