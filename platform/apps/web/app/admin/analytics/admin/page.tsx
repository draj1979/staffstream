"use client";

import { useCallback, useState } from "react";
import * as api from "@/lib/api";
import { useAsync } from "@/hooks/useApi";
import { defaultRange } from "@/lib/date-range";
import { RequireAdmin } from "@/components/admin/RequireAdmin";
import { DateRangePicker } from "@/components/admin/DateRangePicker";
import { InstrumentTile } from "@/components/admin/InstrumentTile";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";

function AdminAnalytics() {
  const [range, setRange] = useState(defaultRange());
  const fetcher = useCallback(() => api.getAdminAnalytics(range.from, range.to), [range.from, range.to]);
  const { data, loading, error, retry } = useAsync(fetcher, [range.from, range.to]);

  const hasActivity = !!data && data.total_conversations > 0;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl">Admin analytics</h1>
          <p className="mt-1 text-sm text-text-muted">The ten-second read on how StaffStream is being used.</p>
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
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <InstrumentTile label="Conversations" value={String(data.total_conversations)} tone="signal" />
            <InstrumentTile
              label="Success rate"
              value={`${Math.round(data.success_rate * 100)}`}
              suffix="%"
              tone="sage"
            />
            <InstrumentTile label="Active employees" value={String(data.active_employees)} tone="brass" />
            <InstrumentTile label="Active agents" value={String(data.active_agents)} tone="signal" />
            <InstrumentTile
              label="Est. cost"
              value={`$${data.total_cost_usd.toFixed(2)}`}
              tone="crimson"
            />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <InstrumentTile
              label="Input tokens"
              value={data.total_input_tokens.toLocaleString()}
              tone="neutral"
            />
            <InstrumentTile
              label="Output tokens"
              value={data.total_output_tokens.toLocaleString()}
              tone="neutral"
            />
          </div>

          {!hasActivity && (
            <div className="mt-8">
              <EmptyState
                title="No activity in this range yet"
                message="Usage will appear here once your team starts chatting with their agents. There's currently no event pipeline feeding this dashboard in production, so zeros here are expected until that's wired up."
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  return (
    <RequireAdmin>
      <AdminAnalytics />
    </RequireAdmin>
  );
}
