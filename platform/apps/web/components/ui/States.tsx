"use client";

import type { CSSProperties, ReactNode } from "react";
import { Button } from "./Button";

export function Skeleton({
  className = "",
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <div className={`animate-pulse rounded-md bg-border/60 ${className}`} style={style} aria-hidden />;
}

export function SkeletonLines({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-2" role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-4 w-full" style={{ width: `${85 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({
  title = "That didn't load",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-md border border-crimson/30 bg-crimson/5 p-4">
      <div>
        <p className="text-sm font-semibold text-crimson">{title}</p>
        <p className="mt-1 text-sm text-text-muted">{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
  icon,
}: {
  title: string;
  message: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-border p-8 text-center">
      {icon}
      <h3 className="font-display text-xl">{title}</h3>
      <p className="max-w-sm text-sm text-text-muted">{message}</p>
      {action}
    </div>
  );
}
