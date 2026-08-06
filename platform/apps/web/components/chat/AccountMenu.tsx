"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { getThemePreference, setThemePreference, type ThemePreference } from "@/lib/theme";

export function AccountMenu() {
  const { employee, role, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<ThemePreference>("system");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => setTheme(getThemePreference()), []);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  function cycleTheme() {
    const next: ThemePreference = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
    setTheme(next);
    setThemePreference(next);
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Account menu"
        aria-expanded={open}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-signal/15 text-sm font-semibold text-signal hover:bg-signal/25"
      >
        {employee?.email?.[0]?.toUpperCase() ?? "?"}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-30 w-64 rounded-md border border-border bg-surface-raised p-3 shadow-panel">
          <p className="text-xs text-text-muted">Signed in as</p>
          <p className="truncate text-sm font-medium text-text-primary">{employee?.email ?? "…"}</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-sage">
            <span className="h-1.5 w-1.5 rounded-full bg-sage" aria-hidden />
            Session active{role ? ` · ${role}` : ""}
          </p>

          <div className="mt-3 flex flex-col gap-0.5 border-t border-border pt-3">
            <Link
              href="/knowledge"
              className="rounded-sm px-2 py-1.5 text-sm text-text-primary hover:bg-bg"
              onClick={() => setOpen(false)}
            >
              Knowledge
            </Link>
            <Link
              href="/connected-skills"
              className="rounded-sm px-2 py-1.5 text-sm text-text-primary hover:bg-bg"
              onClick={() => setOpen(false)}
            >
              Connected apps
            </Link>
            {(role === "manager" || role === "admin") && (
              <Link
                href="/admin/employees"
                className="rounded-sm px-2 py-1.5 text-sm text-text-primary hover:bg-bg"
                onClick={() => setOpen(false)}
              >
                Admin console
              </Link>
            )}
          </div>

          <div className="mt-3 border-t border-border pt-3">
            <button
              onClick={cycleTheme}
              className="w-full rounded-sm px-2 py-1.5 text-left text-sm text-text-primary hover:bg-bg"
            >
              Appearance: {theme === "system" ? "Match device" : theme === "light" ? "Light" : "Dark"}
            </button>
            <button
              onClick={() => logout()}
              className="mt-0.5 w-full rounded-sm px-2 py-1.5 text-left text-sm font-medium text-crimson hover:bg-crimson/10"
            >
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
