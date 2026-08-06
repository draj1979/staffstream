"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";

export function Drawer({
  open,
  onClose,
  title,
  children,
  side = "right",
  widthClass = "max-w-md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  side?: "left" | "right";
  widthClass?: string;
}) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <div
      className={`fixed inset-0 z-40 transition-opacity ${
        open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
      }`}
      aria-hidden={!open}
    >
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`absolute inset-y-0 ${side === "right" ? "right-0" : "left-0"} flex w-full ${widthClass} flex-col border-border bg-surface-raised shadow-panel transition-transform ${
          side === "right" ? "border-l" : "border-r"
        } ${open ? "translate-x-0" : side === "right" ? "translate-x-full" : "-translate-x-full"}`}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="font-display text-lg">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-text-muted hover:bg-bg hover:text-text-primary"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path d="M3 3l12 12M15 3L3 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="thin-scroll flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
