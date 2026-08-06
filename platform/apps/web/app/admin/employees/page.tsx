"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";
import { EmployeeEditDrawer } from "@/components/admin/EmployeeEditDrawer";
import { CreateEmployeeDrawer } from "@/components/admin/CreateEmployeeDrawer";
import { InviteLinkDialog } from "@/components/admin/InviteLinkDialog";
import type { Employee } from "@/lib/types";

const PAGE_SIZE = 25;

export default function AdminEmployeesPage() {
  const { role, employeeId: currentEmployeeId } = useAuth();
  const isAdmin = role === "admin";

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState<Employee | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<{ employee: Employee; kind: "deactivate" | "reactivate" } | null>(
    null
  );
  const [actionLoading, setActionLoading] = useState(false);
  const [inviteState, setInviteState] = useState<{ token: string; expiresIn: number } | null>(null);
  const [invitingId, setInvitingId] = useState<string | null>(null);

  const load = useCallback(async (currentOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const page = await api.listEmployees(PAGE_SIZE, currentOffset);
      setEmployees(page);
      setHasMore(page.length === PAGE_SIZE);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(offset);
  }, [load, offset]);

  function replaceEmployee(updated: Employee) {
    setEmployees((prev) => prev.map((e) => (e.employee_id === updated.employee_id ? updated : e)));
  }

  async function handleInvite(employee: Employee) {
    setInvitingId(employee.employee_id);
    try {
      const result = await api.createInvite(employee.employee_id);
      setInviteState({ token: result.invite_token, expiresIn: result.expires_in });
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't generate an invite link. Try again."));
    } finally {
      setInvitingId(null);
    }
  }

  async function confirmPendingAction() {
    if (!pendingAction) return;
    setActionLoading(true);
    try {
      const updated =
        pendingAction.kind === "deactivate"
          ? await api.deactivateEmployee(pendingAction.employee.employee_id)
          : await api.reactivateEmployee(pendingAction.employee.employee_id);
      replaceEmployee(updated);
      setPendingAction(null);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl">Employees</h1>
          <p className="mt-1 text-sm text-text-muted">
            Manage who has access, invite new teammates, and control roles.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>Add employee</Button>
      </div>

      <div className="mt-6 overflow-hidden rounded-md border border-border bg-surface-raised">
        {loading && (
          <div className="p-5">
            <SkeletonLines count={6} />
          </div>
        )}
        {error && !loading && (
          <div className="p-5">
            <ErrorState message={error} onRetry={() => load(offset)} />
          </div>
        )}
        {!loading && !error && employees.length === 0 && (
          <div className="p-5">
            <EmptyState
              title="No employees yet"
              message="Add your first employee to get started — you can invite them to sign in right after."
              action={<Button onClick={() => setCreateOpen(true)}>Add employee</Button>}
            />
          </div>
        )}
        {!loading && !error && employees.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs font-medium uppercase tracking-wide text-text-muted">
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Designation</th>
                  <th className="px-4 py-3">Roles</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((e) => (
                  <tr key={e.employee_id} className="border-b border-border last:border-0 hover:bg-bg/60">
                    <td className="px-4 py-3 font-medium text-text-primary">
                      {e.email}
                      {e.employee_id === currentEmployeeId && (
                        <span className="ml-2 text-xs text-text-muted">(you)</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-muted">{e.department || "—"}</td>
                    <td className="px-4 py-3 text-text-muted">{e.designation || "—"}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {e.roles.map((r) => (
                          <span
                            key={r}
                            className="rounded-full bg-signal/12 px-2 py-0.5 text-xs font-medium capitalize text-signal"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                          e.active ? "text-sage" : "text-crimson"
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${e.active ? "bg-sage" : "bg-crimson"}`}
                          aria-hidden
                        />
                        {e.active ? "Active" : "Deactivated"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(e)}>
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={invitingId === e.employee_id}
                          onClick={() => handleInvite(e)}
                        >
                          Invite
                        </Button>
                        {e.active ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-crimson"
                            onClick={() => setPendingAction({ employee: e, kind: "deactivate" })}
                          >
                            Deactivate
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-sage"
                            onClick={() => setPendingAction({ employee: e, kind: "reactivate" })}
                          >
                            Reactivate
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!loading && !error && (employees.length > 0 || offset > 0) && (
        <div className="mt-4 flex items-center justify-between">
          <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </Button>
          <p className="font-mono text-xs tabular-nums text-text-muted">
            Showing {offset + 1}–{offset + employees.length}
          </p>
          <Button variant="secondary" size="sm" disabled={!hasMore} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </Button>
        </div>
      )}

      <EmployeeEditDrawer
        employee={editing}
        isAdmin={isAdmin}
        onClose={() => setEditing(null)}
        onSaved={replaceEmployee}
      />
      <CreateEmployeeDrawer
        open={createOpen}
        isAdmin={isAdmin}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => setEmployees((prev) => [created, ...prev])}
      />
      <InviteLinkDialog
        open={!!inviteState}
        token={inviteState?.token ?? null}
        expiresIn={inviteState?.expiresIn ?? null}
        onClose={() => setInviteState(null)}
      />
      <ConfirmDialog
        open={!!pendingAction}
        title={
          pendingAction?.kind === "deactivate"
            ? `Deactivate ${pendingAction.employee.email}?`
            : `Reactivate ${pendingAction?.employee.email}?`
        }
        description={
          pendingAction?.kind === "deactivate"
            ? `${pendingAction.employee.email} will no longer be able to log in. They can be reactivated at any time.`
            : `${pendingAction?.employee.email} will be able to log in again.`
        }
        confirmLabel={pendingAction?.kind === "deactivate" ? "Deactivate" : "Reactivate"}
        destructive={pendingAction?.kind === "deactivate"}
        loading={actionLoading}
        onConfirm={confirmPendingAction}
        onCancel={() => setPendingAction(null)}
      />
    </div>
  );
}
