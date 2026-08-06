"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { EmployeePageShell } from "@/components/layout/EmployeePageShell";
import { KnowledgeContent } from "@/components/chat/KnowledgeContent";

export default function KnowledgePage() {
  return (
    <ProtectedRoute minRole="employee">
      <ErrorBoundary>
        <EmployeePageShell title="Knowledge">
          <KnowledgeContent />
        </EmployeePageShell>
      </ErrorBoundary>
    </ProtectedRoute>
  );
}
