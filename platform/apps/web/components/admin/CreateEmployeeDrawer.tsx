"use client";

import { useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { Drawer } from "@/components/layout/Drawer";
import { Button } from "@/components/ui/Button";
import { FieldGroup, Input } from "@/components/ui/Field";
import type { Employee, Role } from "@/lib/types";

const ALL_ROLES: Role[] = ["admin", "manager", "employee"];

export function CreateEmployeeDrawer({
  open,
  isAdmin,
  onClose,
  onCreated,
}: {
  open: boolean;
  isAdmin: boolean;
  onClose: () => void;
  onCreated: (employee: Employee) => void;
}) {
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [phone, setPhone] = useState("");
  const [roles, setRoles] = useState<Role[]>(["employee"]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setEmail("");
    setDepartment("");
    setDesignation("");
    setPhone("");
    setRoles(["employee"]);
    setError(null);
  }

  function toggleRole(role: Role) {
    setRoles((prev) => (prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]));
  }

  async function handleCreate() {
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await api.createEmployee({
        email: email.trim(),
        department: department || undefined,
        designation: designation || undefined,
        phone: phone || undefined,
        roles: isAdmin ? roles : undefined,
      });
      onCreated(created);
      reset();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't create that employee record. Try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Drawer
      open={open}
      onClose={() => {
        onClose();
      }}
      title="Add employee"
    >
      <div className="flex flex-col gap-4 p-5">
        <p className="text-xs text-text-muted">
          This creates the employee record only — they won&apos;t have login credentials until you send
          them an invite link from the table.
        </p>
        <FieldGroup label="Email" htmlFor="newEmail">
          <Input id="newEmail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </FieldGroup>
        <FieldGroup label="Department" htmlFor="newDepartment">
          <Input id="newDepartment" value={department} onChange={(e) => setDepartment(e.target.value)} />
        </FieldGroup>
        <FieldGroup label="Designation" htmlFor="newDesignation">
          <Input id="newDesignation" value={designation} onChange={(e) => setDesignation(e.target.value)} />
        </FieldGroup>
        <FieldGroup label="Phone" htmlFor="newPhone">
          <Input id="newPhone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </FieldGroup>

        {isAdmin && (
          <div>
            <p className="text-sm font-medium text-text-primary">Roles</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {ALL_ROLES.map((role) => (
                <button
                  key={role}
                  type="button"
                  onClick={() => toggleRole(role)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
                    roles.includes(role)
                      ? "border-signal bg-signal/12 text-signal"
                      : "border-border text-text-muted hover:bg-bg"
                  }`}
                >
                  {role}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && <p className="text-sm text-crimson">{error}</p>}

        <div className="mt-2 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" loading={saving} onClick={handleCreate}>
            Create employee
          </Button>
        </div>
      </div>
    </Drawer>
  );
}
