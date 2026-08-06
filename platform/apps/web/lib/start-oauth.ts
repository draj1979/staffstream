import { getAccessToken } from "./session-store";

/**
 * Kicks off the OAuth "Connect" flow for a skill. See the comment in
 * app/app-api/connections/[skillId]/authorize/route.ts for why this can't
 * be a plain <a href> — this stashes the access token in a same-origin,
 * path-scoped, 30-second cookie the relay route reads and immediately
 * clears, then performs a real top-level navigation.
 */
export function startSkillAuthorize(skillId: string) {
  const token = getAccessToken();
  if (!token) return;
  document.cookie = `ss_authz=${token}; path=/app-api/connections; max-age=30; samesite=lax`;
  window.location.href = `/app-api/connections/${encodeURIComponent(skillId)}/authorize`;
}
