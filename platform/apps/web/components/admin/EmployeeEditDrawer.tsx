"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { Drawer } from "@/components/layout/Drawer";
import { Button } from "@/components/ui/Button";
import { FieldGroup, Input } from "@/components/ui/Field";
import type { Employee, Role } from "@/lib/types";

const ALL_ROLES: Role[] = ["admin", "manager", "employee"];

export function EmployeeEditDrawer({
  employee,
  isAdmin,
  onClose,
  onSaved,
}: {
  employee: Employee | null;
  isAdmin: boolean;
  onClose: () => void;
  onSaved: (updated: Employee) => void;
}) {
  const [email, setEmail] = useState("");
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [phone, setPhone] = useState("");
  const [roles, setRoles] = useState<Role[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!employee) return;
    setEmail(employee.email ?? "");
    setDepartment(employee.department ?? "");
    setDesignation(employee.designation ?? "");
    setPhone(employee.phone ?? "");
    setRoles(employee.roles ?? []);
    setError(null);
  }, [employee]);

  function toggleRole(role: Role) {
    setRoles((prev) => (prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]));
  }

  async function handleSave() {
    if (!employee) return;
    setSaving(true);
    setError(null);
    try {
      const body: Partial<Employee> = {
        email,
        department: department || null,
        designation: designation || null,
        phone: phone || null,
      };
      if (isAdmin) body.roles = roles;
      const updated = await api.updateEmployee(employee.employee_id, body);
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Couldn't save those changes. Try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Drawer open={!!employee} onClose={onClose} title={employee ? `Edit ${employee.email}` : "Edit employee"}>
      {employee && (
        <div className="flex flex-col gap-4 p-5">
          <FieldGroup label="Email" htmlFor="editEmail">
            <Input id="editEmail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </FieldGroup>
          <FieldGroup label="Department" htmlFor="editDepartment">
            <Input id="editDepartment" value={department} onChange={(e) => setDepartment(e.target.value)} />
          </FieldGroup>
          <FieldGroup label="Designation" htmlFor="editDesignation">
            <Input id="editDesignation" value={designation} onChange={(e) => setDesignation(e.target.value)} />
          </FieldGroup>
          <FieldGroup label="Phone" htmlFor="editPhone">
            <Input id="editPhone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </FieldGroup>

          <div>
            <p className="text-sm font-medium text-text-primary">Roles</p>
            {!isAdmin && (
              <p className="mt-1 text-xs text-text-muted">Only admins can change roles.</p>
            )}
            <div className="mt-2 flex flex-wrap gap-2">
              {ALL_ROLES.map((role) => (
                <button
                  key={role}
                  type="button"
                  disabled={!isAdmin}
                  onClick={() => toggleRole(role)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
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

          {error && <p className="text-sm text-crimson">{error}</p>}

          <div className="mt-2 flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button size="sm" loading={saving} onClick={handleSave}>
              Save changes
            </Button>
          </div>
        </div>
      )}
    </Drawer>
  );
}
