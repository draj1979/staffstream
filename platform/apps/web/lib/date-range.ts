export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function defaultRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return { from: isoDate(from), to: isoDate(to) };
}
