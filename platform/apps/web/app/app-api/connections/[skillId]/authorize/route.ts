import { NextRequest, NextResponse } from "next/server";

// -----------------------------------------------------------------------------
// BFF redirect proxy for GET /connections/{skill_id}/authorize.
//
// That backend route requires a Bearer token (see
// services/skill-marketplace/src/skill_marketplace/routers/connections.py),
// but it's meant to be reached via a real top-level browser navigation (it
// 307s to the OAuth provider) — and a plain <a href> can't attach an
// Authorization header to a navigation.
//
// We can't solve this with a plain fetch()+redirect:"manual" from the
// client either: that request is cross-origin (the frontend and
// vartaverse.in are different origins) and browsers deliberately make
// cross-origin opaque redirects unreadable to JS, so we can't recover the
// Location header client-side.
//
// So this route is a small same-origin relay: the client stashes its
// short-lived access token in a cookie scoped to this one path just before
// navigating here, this handler reads it, makes the authenticated request
// to the backend server-side, and forwards the resulting redirect to the
// browser. The relay cookie is cleared in the response whether we succeed
// or fail.
//
// IMPORTANT: `req.url`'s origin is NOT reliable for building our own
// redirect targets here. This Next.js server runs behind Caddy inside
// Docker, and `req.url` resolves against the standalone server's own bind
// address (0.0.0.0:3000) rather than the public Host the browser actually
// requested — the browser then tries to navigate to
// "https://0.0.0.0:3000/..." directly and gets ERR_CONNECTION_REFUSED,
// since nothing is listening on 0.0.0.0 as far as the browser is
// concerned. `BASE_URL` below is the one env var we already trust to be
// this deployment's real public origin (same domain the frontend itself
// is served from, api and app share one Caddy-fronted domain here) — use
// it, not req.url, for every redirect this route issues.
// -----------------------------------------------------------------------------

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://app.staffstream.in";
const RELAY_COOKIE = "ss_authz";

export async function GET(req: NextRequest, { params }: { params: { skillId: string } }) {
  const token = req.cookies.get(RELAY_COOKIE)?.value;
  const clearCookie = { name: RELAY_COOKIE, value: "", path: "/app-api/connections", maxAge: 0 };

  if (!token) {
    const res = NextResponse.redirect(new URL("/connected-skills?connectError=missing_session", BASE_URL));
    res.cookies.set(clearCookie);
    return res;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${BASE_URL}/connections/${encodeURIComponent(params.skillId)}/authorize`, {
      headers: { Authorization: `Bearer ${token}` },
      redirect: "manual",
    });
  } catch {
    const res = NextResponse.redirect(new URL("/connected-skills?connectError=network", BASE_URL));
    res.cookies.set(clearCookie);
    return res;
  }

  const location = upstream.headers.get("location");
  if ((upstream.status === 307 || upstream.status === 302) && location) {
    const res = NextResponse.redirect(location, 307);
    res.cookies.set(clearCookie);
    return res;
  }

  const reason = upstream.status === 403 ? "not_enabled" : upstream.status === 401 ? "unauthorized" : "unknown";
  const res = NextResponse.redirect(new URL(`/connected-skills?connectError=${reason}`, BASE_URL));
  res.cookies.set(clearCookie);
  return res;
}
