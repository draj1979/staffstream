"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAsync } from "@/hooks/useApi";
import { RequireAdmin } from "@/components/admin/RequireAdmin";
import { Button } from "@/components/ui/Button";
import { FieldGroup, Input } from "@/components/ui/Field";
import { ErrorState, SkeletonLines } from "@/components/ui/States";
import type { SsoConfigOut } from "@/lib/types";

const PROVIDERS: Array<{ id: SsoConfigOut["provider"]; label: string }> = [
  { id: "google_workspace", label: "Google Workspace" },
  { id: "auth0", label: "Auth0" },
];

function ProviderCard({ provider, label, existing }: { provider: string; label: string; existing: SsoConfigOut | undefined }) {
  const [clientId, setClientId] = useState(existing?.client_id ?? "");
  const [clientSecret, setClientSecret] = useState("");
  const [issuerDomain, setIssuerDomain] = useState(existing?.issuer_domain ?? "");
  const [hostedDomain, setHostedDomain] = useState(existing?.hosted_domain ?? "");
  const [enabled, setEnabled] = useState(existing?.enabled ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setClientId(existing?.client_id ?? "");
    setIssuerDomain(existing?.issuer_domain ?? "");
    setHostedDomain(existing?.hosted_domain ?? "");
    setEnabled(existing?.enabled ?? false);
  }, [existing]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!clientId.trim() || !clientSecret.trim()) {
      setError("Client ID and client secret are required.");
      return;
    }
    setSaving(true);
    try {
      await api.updateSsoConfig(provider, {
        client_id: clientId.trim(),
        client_secret: clientSecret.trim(),
        issuer_domain: issuerDomain.trim() || undefined,
        hosted_domain: hostedDomain.trim() || undefined,
        enabled,
      });
      setClientSecret("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't save this configuration. Try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSave} className="rounded-md border border-border bg-surface-raised p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg">{label}</h2>
        <label className="flex items-center gap-2 text-sm text-text-primary">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Enabled
        </label>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <FieldGroup label="Client ID" htmlFor={`${provider}-clientId`}>
          <Input id={`${provider}-clientId`} value={clientId} onChange={(e) => setClientId(e.target.value)} />
        </FieldGroup>
        <FieldGroup
          label="Client secret"
          htmlFor={`${provider}-clientSecret`}
          hint={existing?.client_id ? "Leave filled in only when rotating the secret." : undefined}
        >
          <Input
            id={`${provider}-clientSecret`}
            type="password"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            placeholder={existing?.client_id ? "•••••••• (unchanged)" : ""}
          />
        </FieldGroup>
        <FieldGroup label="Issuer domain" htmlFor={`${provider}-issuer`} hint="Optional">
          <Input id={`${provider}-issuer`} value={issuerDomain} onChange={(e) => setIssuerDomain(e.target.value)} />
        </FieldGroup>
        <FieldGroup label="Hosted domain" htmlFor={`${provider}-hosted`} hint="Optional">
          <Input id={`${provider}-hosted`} value={hostedDomain} onChange={(e) => setHostedDomain(e.target.value)} />
        </FieldGroup>
      </div>

      {error && <p className="mt-3 text-sm text-crimson">{error}</p>}
      {saved && <p className="mt-3 text-sm text-sage">Saved.</p>}

      <div className="mt-4 flex justify-end">
        <Button type="submit" size="sm" loading={saving}>
          Save
        </Button>
      </div>
    </form>
  );
}

function SsoSettings() {
  const fetcher = useCallback(() => api.getSsoConfig(), []);
  const { data, loading, error, retry } = useAsync(fetcher, []);

  return (
    <div>
      <h1 className="font-display text-2xl">Single sign-on</h1>
      <p className="mt-1 text-sm text-text-muted">
        Configure Google Workspace and Auth0 for your organization.
      </p>

      {loading && (
        <div className="mt-6">
          <SkeletonLines count={5} />
        </div>
      )}
      {error && (
        <div className="mt-6">
          <ErrorState message={error} onRetry={retry} />
        </div>
      )}
      {!loading && !error && (
        <div className="mt-6 flex flex-col gap-6">
          {PROVIDERS.map((p) => (
            <ProviderCard
              key={p.id}
              provider={p.id}
              label={p.label}
              existing={data?.find((c) => c.provider === p.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SsoPage() {
  return (
    <RequireAdmin>
      <SsoSettings />
    </RequireAdmin>
  );
}
