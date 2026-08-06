type Tone = "signal" | "sage" | "crimson" | "brass" | "neutral";

const toneClasses: Record<Tone, string> = {
  signal: "bg-signal",
  sage: "bg-sage",
  crimson: "bg-crimson",
  brass: "bg-brass",
  neutral: "bg-border",
};

export function InstrumentTile({
  label,
  value,
  suffix,
  tone = "signal",
}: {
  label: string;
  value: string;
  suffix?: string;
  tone?: Tone;
}) {
  return (
    <div className="relative overflow-hidden rounded-md border border-border bg-surface-raised py-3 pl-4 pr-3">
      <span className={`absolute inset-y-0 left-0 w-[3px] ${toneClasses[tone]}`} aria-hidden />
      <p className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-2xl tabular-nums text-text-primary">
        {value}
        {suffix && <span className="ml-1 text-sm text-text-muted">{suffix}</span>}
      </p>
    </div>
  );
}
