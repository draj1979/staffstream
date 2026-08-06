"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AccountMenu } from "@/components/chat/AccountMenu";

export function EmployeePageShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="flex items-center justify-between border-b border-border bg-surface-raised px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            aria-label="Back to chat"
            className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted hover:bg-bg hover:text-text-primary"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path
                d="M11 3 5 9l6 6"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Link>
          <h1 className="font-display text-xl leading-none">{title}</h1>
        </div>
        <AccountMenu />
      </header>
      <div className="thin-scroll mx-auto w-full max-w-2xl flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
