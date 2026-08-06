"use client";

import { AccountMenu } from "./AccountMenu";
import type { Agent } from "@/lib/types";

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted hover:bg-bg hover:text-text-primary"
    >
      {children}
    </button>
  );
}

export function ChatHeader({
  agent,
  onOpenHistory,
  onOpenKnowledge,
  onOpenSkills,
}: {
  agent: Agent | null;
  onOpenHistory: () => void;
  onOpenKnowledge: () => void;
  onOpenSkills: () => void;
}) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-surface-raised px-4 py-3 sm:px-6">
      <div className="flex items-center gap-2.5">
        <span
          className="h-2 w-2 shrink-0 rounded-full bg-brass shadow-[0_0_0_3px_rgba(200,155,60,0.18)]"
          aria-hidden
        />
        <h1 className="font-display text-xl leading-none">{agent?.name ?? "Your agent"}</h1>
      </div>
      <div className="flex items-center gap-1">
        <IconButton label="History" onClick={onOpenHistory}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
            <path
              d="M4 4v4h4M4.2 8a5.8 5.8 0 1 1 1.4 5.9"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </IconButton>
        <IconButton label="Knowledge" onClick={onOpenKnowledge}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
            <path
              d="M3 4.5h5a2 2 0 0 1 2 2V15a1.6 1.6 0 0 0-1.6-1.6H3V4.5ZM15 4.5h-5a2 2 0 0 0-2 2V15a1.6 1.6 0 0 1 1.6-1.6H15V4.5Z"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinejoin="round"
            />
          </svg>
        </IconButton>
        <IconButton label="Connected skills" onClick={onOpenSkills}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
            <path
              d="M9 2.5 10.3 6l3.7.3-2.8 2.4.9 3.6L9 10.4 5.9 12.3l.9-3.6L4 6.3 7.7 6 9 2.5Z"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinejoin="round"
            />
          </svg>
        </IconButton>
        <div className="ml-1">
          <AccountMenu />
        </div>
      </div>
    </header>
  );
}
