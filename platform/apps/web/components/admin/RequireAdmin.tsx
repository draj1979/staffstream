"use client";

import { useAuth } from "@/lib/auth-context";
import { EmptyState } from "@/components/ui/States";

/** Gates admin-only sections of the console (skills, analytics, audit log, SSO). */
export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { role } = useAuth();
  if (role !== "admin") {
    return (
      <div className="p-8">
        <EmptyState
          title="Admins only"
          message="This section is limited to organization admins. Ask an admin if you need access."
        />
      </div>
    );
  }
  return <>{children}</>;
}
