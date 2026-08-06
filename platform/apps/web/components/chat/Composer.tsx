"use client";

import { useRef } from "react";
import type { KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";

export function Composer({
  value,
  onChange,
  onSend,
  disabled,
  error,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
  error?: string | null;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSend();
    }
  }

  return (
    <div className="border-t border-border bg-surface-raised">
      {error && (
        <div className="mx-auto max-w-2xl px-4 pt-3">
          <p className="text-sm text-crimson">{error}</p>
        </div>
      )}
      <div className="mx-auto flex max-w-2xl items-end gap-2 px-4 py-4">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message your agent…"
          rows={1}
          aria-label="Message your agent"
          className="thin-scroll max-h-40 min-h-[2.5rem] flex-1 resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-muted focus:border-signal"
          style={{ height: "auto" }}
          onInput={(e) => {
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
          }}
        />
        <Button onClick={onSend} disabled={disabled || !value.trim()} aria-label="Send message">
          Send
        </Button>
      </div>
    </div>
  );
}
