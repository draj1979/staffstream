"use client";

import { useCallback, useRef, useState } from "react";
import * as api from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useAsync } from "@/hooks/useApi";
import { Button } from "@/components/ui/Button";
import { ErrorState, SkeletonLines } from "@/components/ui/States";
import { FieldGroup, Input, Select } from "@/components/ui/Field";
import type { DocumentOut, DocumentScope } from "@/lib/types";

const STATUS_STYLES: Record<DocumentOut["status"], string> = {
  ready: "bg-sage/15 text-sage",
  processing: "bg-signal/15 text-signal",
  failed: "bg-crimson/15 text-crimson",
};

function DocumentRow({ doc, onDelete, canDelete }: { doc: DocumentOut; onDelete: (id: string) => void; canDelete: boolean }) {
  return (
    <li className="flex items-start justify-between gap-3 border-b border-border py-3 last:border-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-text-primary">{doc.filename}</p>
        <p className="mt-0.5 font-mono text-xs tabular-nums text-text-muted">
          {new Date(doc.created_at).toLocaleDateString()}
        </p>
        {doc.status === "failed" && doc.error_message && (
          <p className="mt-1 text-xs text-crimson">{doc.error_message}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[doc.status]}`}>
          {doc.status}
        </span>
        {canDelete && (
          <button
            onClick={() => onDelete(doc.id)}
            className="text-xs font-medium text-text-muted hover:text-crimson"
            aria-label={`Delete ${doc.filename}`}
          >
            Delete
          </button>
        )}
      </div>
    </li>
  );
}

function DocumentSection({
  title,
  caption,
  scope,
  department,
  employeeId,
  canDelete,
  refreshKey,
  onChanged,
}: {
  title: string;
  caption: string;
  scope: DocumentScope;
  department?: string | null;
  employeeId?: string | null;
  canDelete: boolean;
  refreshKey: number;
  onChanged: () => void;
}) {
  const fetcher = useCallback(
    () =>
      api.listDocuments({
        scope,
        department: scope === "department" ? department ?? undefined : undefined,
        employee_id: scope === "personal" ? employeeId ?? undefined : undefined,
        limit: 50,
      }),
    [scope, department, employeeId]
  );
  const { data, loading, error, retry } = useAsync(fetcher, [refreshKey]);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleDelete(id: string) {
    setDeleting(id);
    try {
      await api.deleteDocument(id);
      onChanged();
    } catch {
      // surfaced implicitly by list staying unchanged; keep it simple here
    } finally {
      setDeleting(null);
    }
  }

  return (
    <section>
      <h3 className="font-display text-lg">{title}</h3>
      <p className="mt-0.5 text-xs text-text-muted">{caption}</p>
      <div className="mt-3">
        {loading && <SkeletonLines count={2} />}
        {error && <ErrorState message={error} onRetry={retry} />}
        {!loading && !error && data && data.length === 0 && (
          <p className="rounded-md border border-dashed border-border p-4 text-sm text-text-muted">
            No documents here yet.
          </p>
        )}
        {!loading && !error && data && data.length > 0 && (
          <ul>
            {data.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                onDelete={handleDelete}
                canDelete={canDelete && deleting !== doc.id}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export function KnowledgeContent() {
  const { employee, role } = useAuth();
  const isAdmin = role === "admin";
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploadScope, setUploadScope] = useState<DocumentScope>("personal");
  const [uploadDepartment, setUploadDepartment] = useState(employee?.department ?? "");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const bump = useCallback(() => setRefreshKey((k) => k + 1), []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    if (uploadScope === "department" && !uploadDepartment.trim()) {
      setUploadError("Department is required for a department-scoped document.");
      return;
    }
    setUploading(true);
    try {
      await api.uploadDocument(file, uploadScope, uploadScope === "department" ? uploadDepartment.trim() : undefined);
      bump();
    } catch (err) {
      setUploadError(apiErrorMessage(err, "That upload failed. Check the file and try again."));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-8 p-5">
      <section className="rounded-md border border-border bg-surface p-4">
        <h3 className="font-display text-lg">Add a document</h3>
        <p className="mt-1 text-xs text-text-muted">
          Uploading blocks until your agent has finished reading it in — that can take a moment for
          longer files.
        </p>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
          <FieldGroup label="Visibility" htmlFor="uploadScope">
            <Select
              id="uploadScope"
              value={uploadScope}
              onChange={(e) => setUploadScope(e.target.value as DocumentScope)}
            >
              <option value="personal">Just me</option>
              {isAdmin && <option value="department">My department</option>}
              {isAdmin && <option value="company">Whole company</option>}
            </Select>
          </FieldGroup>
          {uploadScope === "department" && (
            <FieldGroup label="Department" htmlFor="uploadDepartment">
              <Input
                id="uploadDepartment"
                value={uploadDepartment}
                onChange={(e) => setUploadDepartment(e.target.value)}
                placeholder="e.g. Finance"
              />
            </FieldGroup>
          )}
          <Button
            type="button"
            variant="secondary"
            loading={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            Choose file
          </Button>
          <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} />
        </div>
        {!isAdmin && (
          <p className="mt-2 text-xs text-text-muted">
            You can add documents just for yourself. Company- and department-wide documents are
            managed by an admin.
          </p>
        )}
        {uploadError && <p className="mt-2 text-sm text-crimson">{uploadError}</p>}
      </section>

      <DocumentSection
        title="Company"
        caption="Visible to everyone at your organization."
        scope="company"
        canDelete={isAdmin}
        refreshKey={refreshKey}
        onChanged={bump}
      />
      <DocumentSection
        title="Department"
        caption={employee?.department ? `Visible to ${employee.department}.` : "Set a department to see these."}
        scope="department"
        department={employee?.department}
        canDelete={isAdmin}
        refreshKey={refreshKey}
        onChanged={bump}
      />
      <DocumentSection
        title="Personal"
        caption="Visible only to you."
        scope="personal"
        employeeId={employee?.employee_id}
        canDelete={true}
        refreshKey={refreshKey}
        onChanged={bump}
      />
    </div>
  );
}
