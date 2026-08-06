"use client";

import { useCallback, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAsync } from "@/hooks/useApi";
import { RequireAdmin } from "@/components/admin/RequireAdmin";
import { ErrorState, SkeletonLines } from "@/components/ui/States";
import { CONNECTOR_LABELS, type ConnectorId, type SkillEnablementOut } from "@/lib/types";

function SkillRow({ skill, onToggled }: { skill: SkillEnablementOut; onToggled: (s: SkillEnablementOut) => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = CONNECTOR_LABELS[skill.skill_id as ConnectorId] ?? skill.name;

  async function toggle() {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateSkillEnablement(skill.skill_id, {
        enabled: !skill.enabled,
        config: skill.config ?? {},
      });
      onToggled(updated);
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't update that skill. Try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="flex items-center justify-between gap-4 border-b border-border px-4 py-3 last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-text-primary">{label}</p>
        <p className="mt-0.5 truncate text-xs text-text-muted">{skill.description}</p>
        {error && <p className="mt-1 text-xs text-crimson">{error}</p>}
      </div>
      <button
        role="switch"
        aria-checked={skill.enabled}
        aria-label={`${skill.enabled ? "Turn off" : "Turn on"} ${label}`}
        disabled={saving}
        onClick={toggle}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
          skill.enabled ? "bg-sage" : "bg-border"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
            skill.enabled ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </button>
    </li>
  );
}

function SkillsAdmin() {
  const fetcher = useCallback(() => api.listSkills(), []);
  const { data, loading, error, retry } = useAsync(fetcher, []);
  const [skills, setSkills] = useState<SkillEnablementOut[] | null>(null);
  const list = skills ?? data;

  function handleToggled(updated: SkillEnablementOut) {
    setSkills((list ?? []).map((s) => (s.skill_id === updated.skill_id ? updated : s)));
  }

  return (
    <div>
      <h1 className="font-display text-2xl">Skills</h1>
      <p className="mt-1 text-sm text-text-muted">
        Turn connectors on or off for your whole organization. Employees can connect their own
        account for anything enabled here.
      </p>
      <p className="mt-1 text-xs text-text-muted">
        Note: this API doesn&apos;t expose which individual employees have connected each skill —
        this view shows organization-wide enablement only.
      </p>

      <div className="mt-6 overflow-hidden rounded-md border border-border bg-surface-raised">
        {loading && (
          <div className="p-5">
            <SkeletonLines count={6} />
          </div>
        )}
        {error && (
          <div className="p-5">
            <ErrorState message={error} onRetry={retry} />
          </div>
        )}
        {!loading && !error && list && (
          <ul>
            {list.map((skill) => (
              <SkillRow key={skill.skill_id} skill={skill} onToggled={handleToggled} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function AdminSkillsPage() {
  return (
    <RequireAdmin>
      <SkillsAdmin />
    </RequireAdmin>
  );
}
