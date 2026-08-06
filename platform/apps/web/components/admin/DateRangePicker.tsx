"use client";

import { Input } from "@/components/ui/Field";

export function DateRangePicker({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (range: { from: string; to: string }) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="date"
        value={from}
        aria-label="From date"
        onChange={(e) => onChange({ from: e.target.value, to })}
        className="w-auto"
      />
      <span className="text-sm text-text-muted">to</span>
      <Input
        type="date"
        value={to}
        aria-label="To date"
        onChange={(e) => onChange({ from, to: e.target.value })}
        className="w-auto"
      />
    </div>
  );
}
