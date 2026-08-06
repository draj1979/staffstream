"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import { useAsync } from "@/hooks/useApi";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";
import { startSkillAuthorize } from "@/lib/start-oauth";
import { CONNECTOR_LABELS, type ConnectorId } from "@/lib/types";

const CONNECT_ERROR_MESSAGES: Record<string, string> = {
  missing_session: "Your session expired before the connection could start. Try again.",
  not_enabled: "This skill isn't enabled for your organization anymore.",
  unauthorized: "Your session expired before the connection could start. Try again.",
  network: "Couldn't reach StaffStream to start the connection. Try again.",
  unknown: "That connection attempt didn't go through. Try again.",
};

export function SkillsContent() {
  const params = useSearchParams();
  const [revoking, setRevoking] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const bump = useCallback(() => setRefreshKey((k) => k + 1), []);

  const skillsFetch = useCallback(() => api.listSkills(), []);
  const connectionsFetch = useCallback(() => api.listConnections(), []);
  const skills = useAsync(skillsFetch, [refreshKey]);
  const connections = useAsync(connectionsFetch, [refreshKey]);

  // Refetch connections when we bounce back from an OAuth callback tab close.
  useEffect(() => {
    function onFocus() {
      bump();
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [bump]);

  const connectError = params.get("connectError");

  async function handleDisconnect(skillId: string) {
    setRevoking(skillId);
    try {
      await api.disconnectSkill(skillId);
      bump();
    } finally {
      setRevoking(null);
    }
  }

  const loading = skills.loading || connections.loading;
  const error = skills.error || connections.error;

  const enabled = (skills.data ?? []).filter((s) => s.enabled);
  const connectionBySkill = new Map((connections.data ?? []).map((c) => [c.skill_id, c]));

  return (
    <div className="flex flex-col gap-5 p-5">
      {connectError && (
        <p className="rounded-md border border-crimson/30 bg-crimson/5 p-3 text-sm text-crimson">
          {CONNECT_ERROR_MESSAGES[connectError] ?? CONNECT_ERROR_MESSAGES.unknown}
        </p>
      )}

      <div className="rounded-md border border-brass/30 bg-brass/10 p-3 text-sm text-text-primary">
        A connected skill means your agent can take real actions in that app on your behalf —
        sending messages, creating records, updating tickets — not just talk about it.
      </div>

      {loading && <SkeletonLines count={4} />}
      {error && <ErrorState message={error} onRetry={() => { skills.retry(); connections.retry(); }} />}

      {!loading && !error && enabled.length === 0 && (
        <EmptyState
          title="No skills turned on yet"
          message="Your organization hasn't enabled any connected skills. An admin can turn these on from the admin console."
        />
      )}

      {!loading && !error && enabled.length > 0 && (
        <ul className="flex flex-col gap-2">
          {enabled.map((skill) => {
            const connection = connectionBySkill.get(skill.skill_id);
            const connected = connection?.connected ?? false;
            const label = CONNECTOR_LABELS[skill.skill_id as ConnectorId] ?? skill.name;
            return (
              <li
                key={skill.skill_id}
                className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface p-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary">{label}</p>
                  <p className="mt-0.5 truncate text-xs text-text-muted">
                    {connected
                      ? connection?.external_account
                        ? `Connected as ${connection.external_account}`
                        : "Connected"
                      : skill.description}
                  </p>
                </div>
                {connected ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={revoking === skill.skill_id}
                    onClick={() => handleDisconnect(skill.skill_id)}
                  >
                    Disconnect
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => startSkillAuthorize(skill.skill_id)}
                  >
                    Connect
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
