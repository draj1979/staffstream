"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { FieldGroup, Input, Select } from "@/components/ui/Field";

const PLANS = ["Free", "Team", "Enterprise"];

type Step = "company" | "account" | "done";

export default function OnboardingPage() {
  const router = useRouter();
  const { loginWithTokens } = useAuth();

  const [step, setStep] = useState<Step>("company");
  const [companyName, setCompanyName] = useState("");
  const [plan, setPlan] = useState<string>("Team");
  const [tenantId, setTenantId] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreateTenant(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!companyName.trim()) {
      setError("Company name is required.");
      return;
    }
    setSubmitting(true);
    try {
      const tenant = await api.createTenant({ company_name: companyName.trim(), plan });
      setTenantId(tenant.tenant_id);
      setStep("account");
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't create your organization. Try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!tenantId) return;
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
      const pair = await api.signup(tenantId, { email: email.trim(), password, roles: ["admin"] });
      await loginWithTokens(pair, tenantId);
      setStep("done");
      setTimeout(() => router.replace("/admin/employees"), 900);
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't create your account. Try again."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4 py-12">
      <div className="w-full max-w-md">
        <p className="text-xs font-medium uppercase tracking-wide text-signal">
          Step {step === "company" ? "1" : step === "account" ? "2" : "3"} of 3
        </p>
        <h1 className="mt-1 font-display text-3xl">
          {step === "company" && "Set up your organization"}
          {step === "account" && "Create your admin account"}
          {step === "done" && "You're in"}
        </h1>

        {step === "company" && (
          <form onSubmit={handleCreateTenant} className="mt-8 flex flex-col gap-4" noValidate>
            <FieldGroup label="Company name" htmlFor="companyName">
              <Input
                id="companyName"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Inc."
                required
              />
            </FieldGroup>
            <FieldGroup label="Plan" htmlFor="plan">
              <Select id="plan" value={plan} onChange={(e) => setPlan(e.target.value)}>
                {PLANS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </FieldGroup>
            {error && <p className="text-sm text-crimson">{error}</p>}
            <Button type="submit" loading={submitting} className="mt-2 w-full">
              Continue
            </Button>
          </form>
        )}

        {step === "account" && tenantId && (
          <form onSubmit={handleCreateAccount} className="mt-8 flex flex-col gap-4" noValidate>
            <div className="rounded-md border border-border bg-surface-raised px-3 py-2 text-xs text-text-muted">
              Organization ID (save this — you&apos;ll use it to sign in):
              <p className="mt-1 select-all font-mono text-text-primary">{tenantId}</p>
            </div>
            <FieldGroup label="Your email" htmlFor="email">
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </FieldGroup>
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
              Create account &amp; sign in
            </Button>
          </form>
        )}

        {step === "done" && (
          <p className="mt-8 text-sm text-text-muted">
            Your organization is ready. Taking you to the admin console&hellip;
          </p>
        )}

        {step === "company" && (
          <p className="mt-8 text-center text-sm text-text-muted">
            Already have an organization?{" "}
            <Link href="/login" className="font-medium text-signal hover:underline">
              Sign in
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
