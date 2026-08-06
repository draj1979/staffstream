import type { MemoryTurn } from "./types";

export function dateLabel(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays > 1 && diffDays < 7) {
    return date.toLocaleDateString(undefined, { weekday: "long" });
  }
  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

export interface TurnGroup {
  label: string;
  turns: MemoryTurn[];
}

/** Groups turns (already in chronological order) by calendar day. */
export function groupTurnsByDay(turns: MemoryTurn[]): TurnGroup[] {
  const groups: TurnGroup[] = [];
  for (const turn of turns) {
    const label = dateLabel(turn.created_at);
    const last = groups[groups.length - 1];
    if (last && last.label === label) {
      last.turns.push(turn);
    } else {
      groups.push({ label, turns: [turn] });
    }
  }
  return groups;
}

export function formatClockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
