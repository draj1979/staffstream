// Server-only. client_credentials token for calling other services (e.g. the
// governance microservices, or the Auth0 Management API) as StaffStream
// itself rather than as a signed-in user. Never import this from a Client
// Component — AUTH0_M2M_CLIENT_SECRET must never reach the browser.

interface TokenResponse {
  access_token: string
  expires_in: number
  token_type: string
}

interface CachedToken {
  token: string
  expiresAt: number
}

let cached: CachedToken | null = null

// Refresh a bit before actual expiry so a token doesn't go stale mid-request.
const EXPIRY_SAFETY_MARGIN_MS = 30_000

export async function getM2MToken(audience?: string): Promise<string> {
  const now = Date.now()
  if (cached && cached.expiresAt - EXPIRY_SAFETY_MARGIN_MS > now) {
    return cached.token
  }

  const domain = process.env.AUTH0_DOMAIN
  const clientId = process.env.AUTH0_M2M_CLIENT_ID
  const clientSecret = process.env.AUTH0_M2M_CLIENT_SECRET
  const resolvedAudience = audience ?? process.env.AUTH0_M2M_AUDIENCE

  if (!domain || !clientId || !clientSecret || !resolvedAudience) {
    throw new Error(
      'Missing Auth0 M2M configuration: AUTH0_DOMAIN, AUTH0_M2M_CLIENT_ID, ' +
        'AUTH0_M2M_CLIENT_SECRET, and AUTH0_M2M_AUDIENCE must all be set.'
    )
  }

  const res = await fetch(`https://${domain}/oauth/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      grant_type: 'client_credentials',
      client_id: clientId,
      client_secret: clientSecret,
      audience: resolvedAudience,
    }),
  })

  if (!res.ok) {
    throw new Error(`Auth0 M2M token request failed: ${res.status} ${await res.text()}`)
  }

  const data = (await res.json()) as TokenResponse
  cached = { token: data.access_token, expiresAt: now + data.expires_in * 1000 }
  return cached.token
}
