import { getSession } from '@auth0/nextjs-auth0'
import { withTenantContext, type TenantTx } from '@staffstream/db'
import { AUTH0_COMPANY_ID_CLAIM, AUTH0_ROLE_CLAIM, type AppRole } from './claims'

export class UnauthenticatedError extends Error {
  constructor() {
    super('No active session')
    this.name = 'UnauthenticatedError'
  }
}

export interface CurrentUser {
  sub: string
  email: string | null
  name: string | null
  companyId: string
  role: AppRole
}

/**
 * Reads the Auth0 session for the current request (Server Components, Route
 * Handlers, Server Actions) and normalizes it into the shape the rest of the
 * app needs. Returns null if there is no active session.
 *
 * Throws if the session is missing the company_id custom claim — that means
 * the Auth0 Action that stamps it onto the ID token isn't configured for
 * this tenant, and letting the request through without a company_id would
 * defeat tenant isolation entirely.
 */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const session = await getSession()
  const user = session?.user
  if (!user) return null

  const companyId = user[AUTH0_COMPANY_ID_CLAIM]
  if (!companyId || typeof companyId !== 'string') {
    throw new Error(
      `Auth0 session for user "${user.sub}" is missing the "${AUTH0_COMPANY_ID_CLAIM}" claim. ` +
        'Configure the Auth0 post-login Action that stamps company_id onto the ID token.'
    )
  }

  const role: AppRole = user[AUTH0_ROLE_CLAIM] === 'admin' ? 'admin' : 'employee'

  return {
    sub: user.sub,
    email: user.email ?? null,
    name: user.name ?? null,
    companyId,
    role,
  }
}

/**
 * Convenience wrapper for API routes: resolves the current user and runs
 * `fn` against a DB transaction that has `app.company_id` set via SET LOCAL,
 * so RLS policies enforce tenant isolation. Throws if unauthenticated.
 */
export async function withCurrentUserDb<T>(
  fn: (tx: TenantTx, user: CurrentUser) => Promise<T>
): Promise<T> {
  const user = await getCurrentUser()
  if (!user) {
    throw new UnauthenticatedError()
  }
  return withTenantContext(user.companyId, (tx) => fn(tx, user))
}
