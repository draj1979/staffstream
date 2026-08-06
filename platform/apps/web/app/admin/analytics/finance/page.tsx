"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import * as api from "@/lib/api";
import { useAsync } from "@/hooks/useApi";
import { defaultRange } from "@/lib/date-range";
import { RequireAdmin } from "@/components/admin/RequireAdmin";
import { DateRangePicker } from "@/components/admin/DateRangePicker";
import { InstrumentTile } from "@/components/admin/InstrumentTile";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";
import type { Employee } from "@/lib/types";

function FinanceAnalytics() {
  const [range, setRange] = useState(defaultRange());
  const fetcher = useCallback(() => api.getFinanceAnalytics(range.from, range.to), [range.from, range.to]);
  const { data, loading, error, retry } = useAsync(fetcher, [range.from, range.to]);

  const [names, setNames] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!data || data.cost_by_employee.length === 0) return;
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        data.cost_by_employee.slice(0, 25).map(async (row) => {
          try {
            const emp: Employee = await api.getEmployee(row.employee_id);
            return [row.employee_id, emp.email] as const;
          } catch {
            return [row.employee_id, row.employee_id] as const;
          }
        })
      );
      if (!cancelled) setNames(Object.fromEntries(entries));
    })();
    return () => {
      cancelled = true;
    };
  }, [data]);

  const hasActivity = !!data && data.total_cost_usd > 0;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl">Finance</h1>
          <p className="mt-1 text-sm text-text-muted">Cost by model, by employee, and over time.</p>
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
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <InstrumentTile label="Total cost" value={`$${data.total_cost_usd.toFixed(2)}`} tone="brass" />
            <InstrumentTile label="Input tokens" value={data.total_input_tokens.toLocaleString()} tone="signal" />
            <InstrumentTile label="Output tokens" value={data.total_output_tokens.toLocaleString()} tone="signal" />
          </div>

          {!hasActivity ? (
            <div className="mt-8">
              <EmptyState
                title="No spend in this range yet"
                message="Cost data will appear here once your team starts chatting with their agents. There's currently no event pipeline feeding this dashboard in production, so this is expected to be empty for now."
              />
            </div>
          ) : (
            <div className="mt-8 flex flex-col gap-8">
              <section className="rounded-md border border-border bg-surface-raised p-4">
                <h2 className="font-display text-lg">Daily cost</h2>
                <div className="mt-3 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data.daily_cost}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="day" tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                      <Tooltip
                        formatter={(value: number) => [`$${value.toFixed(2)}`, "Cost"]}
                        contentStyle={{ fontSize: 12, borderRadius: 8 }}
                      />
                      <Line type="monotone" dataKey="cost_usd" stroke="var(--signal)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>

              <section className="rounded-md border border-border bg-surface-raised p-4">
                <h2 className="font-display text-lg">Cost by model</h2>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-text-muted">
                        <th className="py-2 pr-4">Model</th>
                        <th className="py-2 pr-4">Calls</th>
                        <th className="py-2 pr-4">Input tokens</th>
                        <th className="py-2 pr-4">Output tokens</th>
                        <th className="py-2">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono text-xs tabular-nums">
                      {data.cost_by_model.map((row) => (
                        <tr key={row.model} className="border-b border-border last:border-0">
                          <td className="py-2 pr-4 font-sans text-sm text-text-primary">{row.model}</td>
                          <td className="py-2 pr-4">{row.call_count}</td>
                          <td className="py-2 pr-4">{row.input_tokens.toLocaleString()}</td>
                          <td className="py-2 pr-4">{row.output_tokens.toLocaleString()}</td>
                          <td className="py-2">${row.cost_usd.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="rounded-md border border-border bg-surface-raised p-4">
                <h2 className="font-display text-lg">Cost by employee</h2>
                <div className="mt-3 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.cost_by_employee.map((r) => ({ ...r, name: names[r.employee_id] ?? r.employee_id }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--text-muted)" }} interval={0} angle={-20} textAnchor="end" height={60} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--text-muted)" }} />
                      <Tooltip formatter={(value: number) => [`$${value.toFixed(2)}`, "Cost"]} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                      <Bar dataKey="cost_usd" fill="var(--brass)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function FinanceAnalyticsPage() {
  return (
    <RequireAdmin>
      <FinanceAnalytics />
    </RequireAdmin>
  );
}
