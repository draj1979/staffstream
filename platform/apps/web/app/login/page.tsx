"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { FieldGroup, Input } from "@/components/ui/Field";
import { BASE_URL } from "@/lib/api-client";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { loginWithTokens, isAuthenticated, booted } = useAuth();

  const [tenantId, setTenantId] = useState(params.get("tenant_id") ?? params.get("tenant") ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (booted && isAuthenticated) {
      router.replace(params.get("next") ?? "/");
    }
  }, [booted, isAuthenticated, router, params]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!tenantId.trim()) {
      setError("Enter your organization ID — your admin can provide this.");
      return;
    }
    setSubmitting(true);
    try {
      const pair = await api.login(tenantId.trim(), email.trim(), password);
      await loginWithTokens(pair, tenantId.trim());
      router.replace(params.get("next") ?? "/");
    } catch (err) {
      setError(apiErrorMessage(err, "That email and password didn't match. Try again."));
    } finally {
      setSubmitting(false);
    }
  }

  const ssoTenantId = tenantId.trim();

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl">Sign in to StaffStream</h1>
        <p className="mt-2 text-sm text-text-muted">Your personal AI coworker is waiting.</p>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4" noValidate>
          <FieldGroup
            label="Organization ID"
            htmlFor="tenantId"
            hint="Ask your admin for this if you don't have it — there's no company lookup yet."
          >
            <Input
              id="tenantId"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="e.g. 3f2b1c4a-..."
              autoComplete="off"
              required
            />
          </FieldGroup>

          <FieldGroup label="Email" htmlFor="email">
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </FieldGroup>

          <FieldGroup label="Password" htmlFor="password">
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </FieldGroup>

          {error && <p className="text-sm text-crimson">{error}</p>}

          <Button type="submit" loading={submitting} className="mt-2 w-full">
            Sign in
          </Button>
        </form>

        <div className="mt-6 border-t border-border pt-6">
          <p className="text-xs font-medium uppercase tracking-wide text-text-muted">
            Single sign-on
          </p>
          <div className="mt-3 flex flex-col gap-2">
            <a
              href={ssoTenantId ? `${BASE_URL}/auth/sso/login/${ssoTenantId}/google_workspace` : undefined}
              aria-disabled={!ssoTenantId}
              className={`rounded-md border border-border px-4 py-2 text-center text-sm font-medium text-text-primary transition-colors hover:bg-surface-raised ${
                !ssoTenantId ? "pointer-events-none opacity-40" : ""
              }`}
            >
              Continue with Google Workspace
            </a>
            <a
              href={ssoTenantId ? `${BASE_URL}/auth/sso/login/${ssoTenantId}/auth0` : undefined}
              aria-disabled={!ssoTenantId}
              className={`rounded-md border border-border px-4 py-2 text-center text-sm font-medium text-text-primary transition-colors hover:bg-surface-raised ${
                !ssoTenantId ? "pointer-events-none opacity-40" : ""
              }`}
            >
              Continue with Auth0
            </a>
          </div>
          <p className="mt-3 text-xs text-text-muted">
            Enter your organization ID above first. SSO only works for organizations whose
            callback has been configured server-side to redirect back here — check with your
            admin if this doesn&apos;t land you in StaffStream.
          </p>
        </div>

        <p className="mt-8 text-center text-sm text-text-muted">
          Setting up StaffStream for a new company?{" "}
          <Link href="/onboarding" className="font-medium text-signal hover:underline">
            Create an organization
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
