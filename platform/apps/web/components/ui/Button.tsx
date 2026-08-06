"use client";

import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "destructive" | "admin-primary";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary: "bg-brass text-ink hover:brightness-95 active:brightness-90 disabled:opacity-50",
  "admin-primary": "bg-signal text-white hover:brightness-110 active:brightness-95 disabled:opacity-50",
  secondary:
    "bg-transparent border border-border text-text-primary hover:bg-surface-raised disabled:opacity-50",
  ghost: "bg-transparent text-text-primary hover:bg-surface-raised disabled:opacity-50",
  destructive: "bg-crimson text-white hover:brightness-110 active:brightness-95 disabled:opacity-50",
};

const sizeClasses: Record<Size, string> = {
  sm: "text-sm px-3 py-1.5 rounded-sm gap-1.5",
  md: "text-sm px-4 py-2 rounded-md gap-2",
  lg: "text-base px-5 py-2.5 rounded-md gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, className = "", children, disabled, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      className={`inline-flex items-center justify-center font-medium transition-colors disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && (
        <span
          className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden
        />
      )}
      {children}
    </button>
  );
});
