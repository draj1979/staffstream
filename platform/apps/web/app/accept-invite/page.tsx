"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { decodeJwt } from "@/lib/session-store";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { FieldGroup, Input } from "@/components/ui/Field";

function AcceptInviteForm() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const { loginWithTokens } = useAuth();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8 || password.length > 256) {
      setError("Password must be 8-256 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      const pair = await api.acceptInvite(token, password);
      const claims = decodeJwt(pair.access_token);
      if (!claims?.tenant_id) throw new Error("Couldn't read your organization from the invite.");
      await loginWithTokens(pair, claims.tenant_id);
      router.replace("/");
    } catch (err) {
      setError(apiErrorMessage(err, "That invite link isn't valid or has expired. Ask your admin to send a new one."));
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-12">
        <div className="w-full max-w-sm text-center">
          <h1 className="font-display text-2xl">This invite link is incomplete</h1>
          <p className="mt-2 text-sm text-text-muted">
            The link is missing its token. Ask whoever invited you for the full link.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl">Set your password</h1>
        <p className="mt-2 text-sm text-text-muted">
          You&apos;ve been invited to StaffStream. Choose a password to finish setting up your account.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-4" noValidate>
          <FieldGroup label="Password" htmlFor="password" hint="8-256 characters.">
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </FieldGroup>
          <FieldGroup label="Confirm password" htmlFor="confirmPassword">
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </FieldGroup>
          {error && <p className="text-sm text-crimson">{error}</p>}
          <Button type="submit" loading={submitting} className="mt-2 w-full">
            Set password &amp; sign in
          </Button>
        </form>
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={null}>
      <AcceptInviteForm />
    </Suspense>
  );
}
