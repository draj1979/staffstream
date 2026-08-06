"use client";

import { Suspense } from "react";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EmployeePageShell } from "@/components/layout/EmployeePageShell";
import { SkillsContent } from "@/components/chat/SkillsContent";
import { SkeletonLines } from "@/components/ui/States";

export default function SkillsPage() {
  return (
    <ProtectedRoute minRole="employee">
      <ErrorBoundary>
        <EmployeePageShell title="Connected apps">
          <Suspense fallback={<div className="p-5"><SkeletonLines count={4} /></div>}>
            <SkillsContent />
          </Suspense>
        </EmployeePageShell>
      </ErrorBoundary>
    </ProtectedRoute>
  );
}
