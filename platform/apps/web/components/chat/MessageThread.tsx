"use client";

import { useEffect, useRef } from "react";
import { formatClockTime, groupTurnsByDay } from "@/lib/date-grouping";
import type { MemoryTurn } from "@/lib/types";

export interface ChatMessage extends MemoryTurn {
  pending?: boolean;
  failed?: boolean;
}

export function ThinkingDot() {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden>
      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brass" />
      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brass [animation-delay:0.2s]" />
      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brass [animation-delay:0.4s]" />
    </span>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-2.5 text-sm leading-relaxed sm:max-w-[70%] ${
          isUser
            ? "bg-brass text-ink"
            : message.failed
            ? "border border-crimson/40 bg-crimson/5 text-text-primary"
            : "border border-border bg-surface text-text-primary"
        }`}
      >
        {message.pending ? (
          <ThinkingDot />
        ) : (
          <p className="whitespace-pre-wrap">{message.content}</p>
        )}
        {!message.pending && (
          <p
            className={`mt-1 font-mono text-[11px] tabular-nums ${
              isUser ? "text-ink/60" : "text-text-muted"
            }`}
          >
            {formatClockTime(message.created_at)}
            {message.failed && <span className="ml-2 text-crimson">Not sent — try again</span>}
          </p>
        )}
      </div>
    </div>
  );
}

export function MessageThread({ messages }: { messages: ChatMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const lastMessage = messages[messages.length - 1];
  const lastMessageContent = lastMessage?.content;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, lastMessageContent]);

  const groups = groupTurnsByDay(messages);

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-6">
      {groups.map((group) => (
        <div key={group.label} className="flex flex-col gap-3">
          <p className="text-center text-xs font-medium uppercase tracking-wide text-text-muted">
            {group.label}
          </p>
          {group.turns.map((turn) => (
            <Bubble key={turn.id} message={turn as ChatMessage} />
          ))}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
