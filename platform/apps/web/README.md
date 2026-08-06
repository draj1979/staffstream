# StaffStream — Web

Next.js 14 (App Router, TypeScript) frontend for StaffStream: an employee-facing
chat home where every employee talks to their personal AI agent, and an admin
console for running the organization (employees, connectors, analytics, audit
log, SSO).

## Running locally

```bash
cd apps/web
npm install
cp .env.local.example .env.local
npm run dev
```

### Environment variables (`.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Base origin for the backend. Everything (auth, employees, tenants, agents, chat, memory, documents, skills, connections) is routed through this origin — `https://vartaverse.in` in the live pilot. `/analytics/*` and `/audit-logs*` are also called against this same origin, just without the API-gateway path-prefix rewrite the other routes get server-side. |

### Scripts

- `npm run dev` — local dev server
- `npm run build` — production build (also runs type checking + linting)
- `npm run start` — serve a production build
- `npm run typecheck` — `tsc --noEmit`
- `npm run lint` — ESLint

## Structure

```
app/
  login/                    Sign-in (org ID + email/password + SSO entry points)
  onboarding/               New-tenant creation → first admin account, 2-step flow
  accept-invite/            "Set your password" landing page for invite links
  page.tsx                  Chat home (employee)
  knowledge/                Full-page knowledge screen (also available as a drawer)
  skills/                   Full-page connected-skills screen (also a drawer)
  admin/                    Admin console route group (rail nav layout)
    employees/              List, invite, deactivate/reactivate, edit
    skills/                 Tenant-wide connector enable/disable
    analytics/{admin,finance,it}/   The three analytics dashboards
    audit-log/              Filterable audit log table
    sso/                    Google Workspace / Auth0 configuration
  app-api/connections/[skillId]/authorize/route.ts
                            Same-origin redirect relay for the OAuth "Connect"
                            flow (see comment in the file for why this exists)
components/
  chat/                     Chat header, message thread, composer, drawers content
  admin/                    Rail nav, instrument tiles, employee dialogs, etc.
  layout/                   Drawer/sheet primitive, employee page shell
  ui/                       Button, Field, States (loading/empty/error), dialogs
  auth/                     Route-level auth/role gating
lib/
  api-client.ts             Low-level fetch wrapper: auth header, 401→refresh→retry→redirect
  api.ts                    Typed functions for every backend endpoint
  session-store.ts          In-memory access token + localStorage refresh token
  auth-context.tsx          React context: session boot, proactive refresh, current employee/role
  types.ts                  Backend response/request types
```

## Design system

Colors, type, and layout follow the brief exactly: Fraunces for display
moments only (agent name, section titles, empty-state headlines), IBM Plex
Sans for everything else, IBM Plex Mono with tabular numerals for anything
numeric. Brass is the employee/agent accent; Signal is the admin accent — they
never share a job. All of it lives in `app/globals.css` (CSS custom
properties, light/dark via `prefers-color-scheme` and a `data-theme`
override) and `tailwind.config.ts` (theme extension referencing those same
variables).

## Known limitations

These are inherent to the current backend, not gaps in this frontend:

- **Chat is not streaming.** `/chat` is a single blocking request/response, so
  the UI shows a calm "thinking" pulse rather than a token-by-token typing
  effect.
- **No cross-conversation search.** The memory service models one continuous
  turn history per agent, not separate named conversations. The history
  drawer filters what's already loaded client-side — it's "search in this
  conversation," not a server-side search across conversations.
- **No memory/knowledge citations.** `/chat` responses carry no metadata
  about which documents or memories were used, so nothing in the UI claims a
  specific message used a specific document. What the agent has access to is
  shown as a standing Knowledge panel instead.
- **No per-employee skill-connection visibility for admins.** `GET /skills`
  gives tenant-wide enablement; there's no endpoint for an admin to see which
  individual employees have connected which skill. The admin Skills screen
  says so in a caption rather than fabricating that data.
- **Analytics and audit log will likely show empty states.** There is
  currently no message broker feeding the event pipeline in production, so
  `/analytics/*` and `/audit-logs` will plausibly return real-but-empty data.
  Every chart and table has a genuine empty state for this rather than
  assuming data will be there.
- **Invite links must be delivered manually.** There's no email service.
  Admins get a "copy link" affordance and are expected to send it via
  whatever channel they already use.
- **SSO callback quirk.** `GET /auth/sso/callback/{provider}` currently
  returns a `TokenPair` as raw JSON at a GET URL instead of redirecting to a
  frontend page (a known backend limitation from before this frontend
  existed). `/login` accepts a `?tenant_id=` query param to prefill the
  organization ID and builds the SSO links from it, but actually completing
  SSO requires that backend redirect to be fixed server-side first — the
  login screen says so under the SSO buttons.

## A backend quirk this frontend had to work around

`GET /connections/{skill_id}/authorize` (the "Connect" button for a skill)
requires a `Bearer` token, but it's meant to be reached via a real top-level
browser navigation, since it 307-redirects to the external OAuth provider. A
plain `<a href>` can't attach an Authorization header, and a client-side
`fetch()` with `redirect: "manual"` can't recover the target `Location` for a
cross-origin response — browsers deliberately hide it.

The fix is a small same-origin BFF relay at
`app/app-api/connections/[skillId]/authorize/route.ts`: the client stashes
its access token in a cookie scoped to that one path for 30 seconds
(`lib/start-oauth.ts`), navigates there, the route handler reads the cookie,
calls the backend server-side with the header, forwards the resulting
redirect, and clears the cookie either way. Full rationale is in the comments
at the top of that route file.
