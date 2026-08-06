"use client";

import { useCallback, useState } from "react";
import * as api from "@/lib/api";
import { useAsync } from "@/hooks/useApi";
import { RequireAdmin } from "@/components/admin/RequireAdmin";
import { FieldGroup, Input, Select } from "@/components/ui/Field";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";
import type { AuditAction } from "@/lib/types";

const ACTIONS: AuditAction[] = [
  "sso.config_changed",
  "agent.updated",
  "skill.enablement_changed",
  "skill.connected",
  "skill.disconnected",
  "tenant.updated",
  "employee.created",
  "employee.updated",
  "employee.role_changed",
  "employee.deactivated",
  "employee.reactivated",
];

function AuditLog() {
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const [actorId, setActorId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const fetcher = useCallback(
    () =>
      api.getAuditLogs({
        action: action || undefined,
        target_type: targetType || undefined,
        actor_employee_id: actorId || undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        limit: 100,
      }),
    [action, targetType, actorId, fromDate, toDate]
  );
  const { data, loading, error, retry } = useAsync(fetcher, [action, targetType, actorId, fromDate, toDate]);

  return (
    <div>
      <h1 className="font-display text-2xl">Audit log</h1>
      <p className="mt-1 text-sm text-text-muted">
        Every state-changing action taken across your organization.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-3 rounded-md border border-border bg-surface-raised p-4">
        <FieldGroup label="Action" htmlFor="filterAction">
          <Select id="filterAction" value={action} onChange={(e) => setAction(e.target.value)} className="w-56">
            <option value="">All actions</option>
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </Select>
        </FieldGroup>
        <FieldGroup label="Target type" htmlFor="filterTargetType">
          <Input
            id="filterTargetType"
            value={targetType}
            onChange={(e) => setTargetType(e.target.value)}
            placeholder="e.g. employee"
            className="w-40"
          />
        </FieldGroup>
        <FieldGroup label="Actor employee ID" htmlFor="filterActor">
          <Input id="filterActor" value={actorId} onChange={(e) => setActorId(e.target.value)} className="w-52" />
        </FieldGroup>
        <FieldGroup label="From" htmlFor="filterFrom">
          <Input id="filterFrom" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="w-auto" />
        </FieldGroup>
        <FieldGroup label="To" htmlFor="filterTo">
          <Input id="filterTo" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="w-auto" />
        </FieldGroup>
      </div>

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
        {!loading && !error && data && data.length === 0 && (
          <div className="p-5">
            <EmptyState
              title="Nothing to show yet"
              message="There's currently no event pipeline feeding audit entries in production, so this list is expected to be empty until that's wired up — or try widening your filters."
            />
          </div>
        )}
        {!loading && !error && data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-text-muted">
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Target</th>
                  <th className="px-4 py-3">Actor</th>
                </tr>
              </thead>
              <tbody className="font-mono text-xs tabular-nums">
                {data.map((entry) => (
                  <tr key={entry.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">{new Date(entry.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 font-sans text-sm text-text-primary">{entry.action}</td>
                    <td className="px-4 py-3">
                      {entry.target_type} · {entry.target_id}
                    </td>
                    <td className="px-4 py-3">{entry.actor_employee_id ?? "system"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuditLogPage() {
  return (
    <RequireAdmin>
      <AuditLog />
    </RequireAdmin>
  );
}
