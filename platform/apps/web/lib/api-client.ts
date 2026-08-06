import {
  clearSession,
  getAccessToken,
  getStoredRefreshToken,
  getTenantId,
  setTokenPair,
} from "./session-store";
import type { ApiErrorBody, TokenPair } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://vartaverse.in";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | null;

  constructor(status: number, message: string, body: ApiErrorBody | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function apiErrorMessage(err: unknown, fallback = "Something went wrong. Try again."): string {
  if (err instanceof ApiError) {
    if (err.body?.error_message) return err.body.error_message;
    const detail = err.body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d) => d.msg).join("; ");
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip attaching Authorization (login/signup/refresh/invite-accept/tenant-create). */
  unauthenticated?: boolean;
  /** Explicit X-Tenant-Id override (login/signup, before a session exists). */
  tenantId?: string;
  /** Don't attempt the silent-refresh-and-retry dance (used by /auth/refresh itself). */
  skipRefreshRetry?: boolean;
  /** Pass a FormData body as-is without JSON-encoding / content-type override. */
  isFormData?: boolean;
}

let refreshInFlight: Promise<TokenPair | null> | null = null;

async function performRefresh(): Promise<TokenPair | null> {
  const refreshToken = getStoredRefreshToken();
  const tenantId = getTenantId();
  if (!refreshToken || !tenantId) return null;
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Tenant-Id": tenantId,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const pair = (await res.json()) as TokenPair;
    setTokenPair(pair, tenantId);
    return pair;
  } catch {
    return null;
  }
}

/** Ensures at most one /auth/refresh call is in flight at a time. */
export function refreshSession(): Promise<TokenPair | null> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

function redirectToLogin() {
  clearSession();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?next=${next}`;
  }
}

async function doFetch(path: string, options: RequestOptions): Promise<Response> {
  const headers = new Headers(options.headers);
  const tenantId = options.tenantId ?? getTenantId();
  if (tenantId && !headers.has("X-Tenant-Id")) headers.set("X-Tenant-Id", tenantId);

  if (!options.unauthenticated) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  let body: BodyInit | undefined;
  if (options.isFormData) {
    body = options.body as FormData;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  return fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
    body,
  });
}

/**
 * Core typed request helper. Attaches the bearer token, retries once via a
 * silent /auth/refresh on a 401, and redirects to /login if that also fails
 * (or if the request needed a session that never existed).
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res = await doFetch(path, options);

  if (res.status === 401 && !options.unauthenticated && !options.skipRefreshRetry) {
    const refreshed = await refreshSession();
    if (refreshed) {
      res = await doFetch(path, options);
    } else {
      redirectToLogin();
      throw new ApiError(401, "Session expired", null);
    }
  }

  if (res.status === 401 && !options.unauthenticated) {
    redirectToLogin();
    throw new ApiError(401, "Session expired", null);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  const data = text ? safeJsonParse(text) : null;

  if (!res.ok) {
    throw new ApiError(res.status, res.statusText, data as ApiErrorBody | null);
  }

  return data as T;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export { BASE_URL };
