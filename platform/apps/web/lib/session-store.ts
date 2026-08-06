import type { JwtClaims, Role, TokenPair } from "./types";

// ---------------------------------------------------------------------------
// Session persistence.
//
// Access tokens live only in memory for the tab's lifetime (a module-level
// variable + a tiny pub/sub so React components re-render on change).
//
// Refresh tokens are persisted to localStorage so a page reload doesn't force
// a re-login. This is a deliberate, demo/pilot-appropriate tradeoff: a
// long-lived (30 day) bearer credential sitting in localStorage is readable
// by any script that achieves XSS on this origin. A production hardening
// pass would move this to an httpOnly cookie minted by a same-origin BFF
// endpoint, which this backend does not currently expose. We rotate the
// refresh token on every use (the backend issues single-use/rotating
// refresh tokens) and clear it on logout to limit the blast radius.
// ---------------------------------------------------------------------------

const REFRESH_TOKEN_KEY = "staffstream.refresh_token";
const TENANT_ID_KEY = "staffstream.tenant_id";

interface SessionState {
  accessToken: string | null;
  tenantId: string | null;
  claims: JwtClaims | null;
}

let state: SessionState = {
  accessToken: null,
  tenantId: typeof window !== "undefined" ? localStorage.getItem(TENANT_ID_KEY) : null,
  claims: null,
};

type Listener = (state: SessionState) => void;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l(state);
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getState(): SessionState {
  return state;
}

export function decodeJwt(token: string): JwtClaims | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
    const json = typeof window !== "undefined" ? window.atob(padded) : atob(padded);
    return JSON.parse(json) as JwtClaims;
  } catch {
    return null;
  }
}

export function setTokenPair(pair: TokenPair, tenantId?: string) {
  const claims = decodeJwt(pair.access_token);
  state = {
    accessToken: pair.access_token,
    tenantId: tenantId ?? claims?.tenant_id ?? state.tenantId,
    claims,
  };
  if (typeof window !== "undefined") {
    localStorage.setItem(REFRESH_TOKEN_KEY, pair.refresh_token);
    if (state.tenantId) localStorage.setItem(TENANT_ID_KEY, state.tenantId);
  }
  emit();
}

export function setTenantId(tenantId: string) {
  state = { ...state, tenantId };
  if (typeof window !== "undefined") localStorage.setItem(TENANT_ID_KEY, tenantId);
  emit();
}

export function getAccessToken(): string | null {
  return state.accessToken;
}

export function getTenantId(): string | null {
  return state.tenantId;
}

export function getRole(): Role | null {
  return (state.claims?.role as Role) ?? null;
}

export function getEmployeeId(): string | null {
  return state.claims?.sub ?? null;
}

export function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearSession() {
  state = { accessToken: null, tenantId: state.tenantId, claims: null };
  if (typeof window !== "undefined") {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
  emit();
}

/** True if the current access token is missing or within `skewMs` of expiry. */
export function isAccessTokenStale(skewMs = 30_000): boolean {
  if (!state.accessToken || !state.claims) return true;
  const expiresAt = state.claims.exp * 1000;
  return Date.now() >= expiresAt - skewMs;
}
