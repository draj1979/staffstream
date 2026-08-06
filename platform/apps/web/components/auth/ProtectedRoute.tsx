"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import type { Role } from "@/lib/types";
import { SkeletonLines } from "@/components/ui/States";

const ROLE_RANK: Record<Role, number> = { employee: 0, manager: 1, admin: 2 };

export function ProtectedRoute({
  children,
  minRole = "employee",
}: {
  children: React.ReactNode;
  minRole?: Role;
}) {
  const { booted, isAuthenticated, role } = useAuth();
  const router = useRouter();

  const roleOk = role ? ROLE_RANK[role] >= ROLE_RANK[minRole] : false;

  useEffect(() => {
    if (!booted) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (role && !roleOk) {
      router.replace("/");
    }
  }, [booted, isAuthenticated, role, roleOk, router]);

  if (!booted || !isAuthenticated || (role && !roleOk)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg p-6">
        <div className="w-full max-w-sm">
          <SkeletonLines count={4} />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
