"use client";

import { useMemo, useState } from "react";
import { formatClockTime, groupTurnsByDay } from "@/lib/date-grouping";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";
import { Input } from "@/components/ui/Field";
import type { MemoryTurn } from "@/lib/types";

export function HistoryContent({
  turns,
  loading,
  error,
  onRetry,
}: {
  turns: MemoryTurn[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!turns) return [];
    if (!query.trim()) return turns;
    const q = query.trim().toLowerCase();
    return turns.filter((t) => t.content.toLowerCase().includes(q));
  }, [turns, query]);

  const groups = useMemo(() => groupTurnsByDay(filtered), [filtered]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-4">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search in this conversation"
          aria-label="Search in this conversation"
        />
        <p className="mt-1.5 text-xs text-text-muted">
          Filters what&apos;s already loaded below — this isn&apos;t a search across separate conversations,
          there&apos;s just the one continuous thread with your agent.
        </p>
      </div>
      <div className="thin-scroll flex-1 overflow-y-auto p-4">
        {loading && <SkeletonLines count={5} />}
        {error && <ErrorState message={error} onRetry={onRetry} />}
        {!loading && !error && groups.length === 0 && (
          <EmptyState
            title={query ? "No matches" : "No conversation yet"}
            message={
              query
                ? "Nothing in this conversation matches that search."
                : "Once you and your agent start talking, it'll show up here."
            }
          />
        )}
        {!loading &&
          !error &&
          groups.map((group) => (
            <div key={group.label} className="mb-5">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                {group.label}
              </p>
              <ul className="flex flex-col gap-2">
                {group.turns.map((turn) => (
                  <li key={turn.id} className="rounded-md border border-border bg-surface p-2.5 text-sm">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xs font-medium text-text-muted">
                        {turn.role === "user" ? "You" : "Agent"}
                      </span>
                      <span className="font-mono text-xs tabular-nums text-text-muted">
                        {formatClockTime(turn.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 whitespace-pre-wrap text-text-primary">{turn.content}</p>
                  </li>
                ))}
              </ul>
            </div>
          ))}
      </div>
    </div>
  );
}
