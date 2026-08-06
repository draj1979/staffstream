"use client";

import { useCallback, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import * as api from "@/lib/api";
import { useAsync } from "@/hooks/useApi";
import { defaultRange } from "@/lib/date-range";
import { RequireAdmin } from "@/components/admin/RequireAdmin";
import { DateRangePicker } from "@/components/admin/DateRangePicker";
import { InstrumentTile } from "@/components/admin/InstrumentTile";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";

function ItAnalytics() {
  const [range, setRange] = useState(defaultRange());
  const fetcher = useCallback(() => api.getItAnalytics(range.from, range.to), [range.from, range.to]);
  const { data, loading, error, retry } = useAsync(fetcher, [range.from, range.to]);

  const hasActivity = !!data && data.total_requests > 0;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl">IT</h1>
          <p className="mt-1 text-sm text-text-muted">Request volume, latency, and where errors happen.</p>
        </div>
        <DateRangePicker from={range.from} to={range.to} onChange={setRange} />
      </div>

      {loading && (
        <div className="mt-6">
          <SkeletonLines count={4} />
        </div>
      )}
      {error && (
        <div className="mt-6">
          <ErrorState message={error} onRetry={retry} />
        </div>
      )}
      {!loading && !error && data && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <InstrumentTile label="Requests" value={String(data.total_requests)} tone="signal" />
            <InstrumentTile
              label="Error rate"
              value={`${Math.round(data.error_rate * 100)}`}
              suffix="%"
              tone={data.error_rate > 0.05 ? "crimson" : "sage"}
            />
            <InstrumentTile label="Avg latency" value={String(Math.round(data.avg_latency_ms))} suffix="ms" tone="neutral" />
            <InstrumentTile label="P95 latency" value={String(Math.round(data.p95_latency_ms))} suffix="ms" tone="neutral" />
          </div>

          {!hasActivity ? (
            <div className="mt-8">
              <EmptyState
                title="No requests in this range yet"
                message="Request and latency data will appear here once your team starts chatting with their agents. There's currently no event pipeline feeding this dashboard in production, so this is expected to be empty for now."
              />
            </div>
          ) : (
            <div className="mt-8 flex flex-col gap-8">
              <section className="rounded-md border border-border bg-surface-raised p-4">
                <h2 className="font-display text-lg">Requests by agent</h2>
                <div className="mt-3 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.requests_by_agent}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="agent_id" tick={{ fontSize: 10, fill: "var(--text-muted)" }} hide />
                      <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                      <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                      <Bar dataKey="request_count" name="Requests" fill="var(--signal)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="error_count" name="Errors" fill="var(--crimson)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="rounded-md border border-border bg-surface-raised p-4">
                <h2 className="font-display text-lg">Errors by stage</h2>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-text-muted">
                        <th className="py-2 pr-4">Stage</th>
                        <th className="py-2">Count</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono text-xs tabular-nums">
                      {data.errors_by_stage.map((row) => (
                        <tr key={row.error_stage} className="border-b border-border last:border-0">
                          <td className="py-2 pr-4 font-sans text-sm text-text-primary">{row.error_stage}</td>
                          <td className="py-2">{row.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function ItAnalyticsPage() {
  return (
    <RequireAdmin>
      <ItAnalytics />
    </RequireAdmin>
  );
}
