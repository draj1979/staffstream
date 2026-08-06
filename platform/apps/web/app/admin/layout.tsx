"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { AdminRail } from "@/components/admin/AdminRail";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute minRole="manager">
      <div className="flex min-h-screen bg-bg">
        <AdminRail />
        <main className="thin-scroll flex-1 overflow-y-auto">
          <ErrorBoundary>
            <div className="mx-auto max-w-6xl px-6 py-8 sm:px-8">{children}</div>
          </ErrorBoundary>
        </main>
      </div>
    </ProtectedRoute>
  );
}
