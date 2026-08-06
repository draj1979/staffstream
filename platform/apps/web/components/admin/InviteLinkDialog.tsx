"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { BASE_URL } from "@/lib/api-client";

export function InviteLinkDialog({
  open,
  token,
  expiresIn,
  onClose,
}: {
  open: boolean;
  token: string | null;
  expiresIn: number | null;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  if (!open || !token) return null;

  const link = `${BASE_URL}/accept-invite?token=${encodeURIComponent(token)}`;
  const hours = expiresIn ? Math.round(expiresIn / 3600) : null;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API unavailable — the link is still selectable in the field
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-lg border border-border bg-surface-raised p-5 shadow-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-text-primary">Invite link ready</h2>
        <p className="mt-1.5 text-sm text-text-muted">
          There&apos;s no email service in StaffStream yet — copy this link and send it however you
          currently reach this person (Slack, email, text).
          {hours && ` It expires in about ${hours} hour${hours === 1 ? "" : "s"}.`}
        </p>
        <div className="mt-3 flex items-center gap-2">
          <input
            readOnly
            value={link}
            onFocus={(e) => e.currentTarget.select()}
            className="w-full select-all truncate rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-text-primary"
          />
          <Button variant="secondary" size="sm" onClick={handleCopy}>
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
        <div className="mt-5 flex justify-end">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </div>
  );
}
