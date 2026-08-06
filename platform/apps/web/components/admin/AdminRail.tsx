"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

interface NavItem {
  href: string;
  label: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/admin/employees", label: "Employees" },
  { href: "/admin/skills", label: "Skills", adminOnly: true },
  { href: "/admin/analytics/admin", label: "Analytics", adminOnly: true },
  { href: "/admin/analytics/finance", label: "Finance", adminOnly: true },
  { href: "/admin/analytics/it", label: "IT", adminOnly: true },
  { href: "/admin/audit-log", label: "Audit log", adminOnly: true },
  { href: "/admin/sso", label: "SSO", adminOnly: true },
];

export function AdminRail() {
  const pathname = usePathname();
  const { role, employee, logout } = useAuth();
  const isAdmin = role === "admin";

  return (
    <nav className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-surface-raised">
      <div className="border-b border-border px-5 py-5">
        <Link href="/" className="font-display text-xl">
          StaffStream
        </Link>
        <p className="mt-0.5 text-xs text-text-muted">Admin console</p>
      </div>
      <ul className="flex-1 overflow-y-auto py-3">
        {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => {
          const active = pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`mx-2 mb-0.5 flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-signal/12 text-signal" : "text-text-primary hover:bg-bg"
                }`}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-border p-4">
        <p className="truncate text-xs text-text-muted">{employee?.email}</p>
        <p className="mt-0.5 flex items-center gap-1.5 text-xs text-sage">
          <span className="h-1.5 w-1.5 rounded-full bg-sage" aria-hidden />
          Session active
        </p>
        <div className="mt-2 flex items-center gap-3">
          <Link href="/" className="text-xs font-medium text-signal hover:underline">
            Back to chat
          </Link>
          <button onClick={() => logout()} className="text-xs font-medium text-crimson hover:underline">
            Log out
          </button>
        </div>
      </div>
    </nav>
  );
}
