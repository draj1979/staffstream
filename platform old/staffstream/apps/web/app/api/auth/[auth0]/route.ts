import { handleAuth } from '@auth0/nextjs-auth0'

// Handles /api/auth/login, /api/auth/logout, /api/auth/callback (and the
// SDK's own /api/auth/me, though that's shadowed by our custom
// app/api/auth/me/route.ts — Next.js resolves the static route first).
export const GET = handleAuth()
