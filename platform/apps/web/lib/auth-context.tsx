"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getEmployee } from "./api";
import { refreshSession } from "./api-client";
import {
  clearSession,
  getAccessToken,
  getEmployeeId,
  getRole,
  getStoredRefreshToken,
  getTenantId,
  setTenantId as persistTenantId,
  setTokenPair,
  subscribe,
} from "./session-store";
import * as api from "./api";
import type { Employee, Role, TokenPair } from "./types";

interface AuthContextValue {
  /** null = not booted yet, undefined-ish states handled via `booted` */
  booted: boolean;
  isAuthenticated: boolean;
  employee: Employee | null;
  role: Role | null;
  employeeId: string | null;
  tenantId: string | null;
  refreshingEmployee: boolean;
  loginWithTokens: (pair: TokenPair, tenantId: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadEmployee: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [booted, setBooted] = useState(false);
  const [accessToken, setAccessToken] = useState<string | null>(getAccessToken());
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [refreshingEmployee, setRefreshingEmployee] = useState(false);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return subscribe((s) => setAccessToken(s.accessToken));
  }, []);

  const reloadEmployee = useCallback(async () => {
    const id = getEmployeeId();
    if (!id) {
      setEmployee(null);
      return;
    }
    setRefreshingEmployee(true);
    try {
      const emp = await getEmployee(id);
      setEmployee(emp);
    } catch {
      // Leave stale employee data rather than blanking the UI on a
      // transient failure; screens that need fresh role data will retry.
    } finally {
      setRefreshingEmployee(false);
    }
  }, []);

  const loginWithTokens = useCallback(
    async (pair: TokenPair, tenantId: string) => {
      persistTenantId(tenantId);
      setTokenPair(pair, tenantId);
      await reloadEmployee();
    },
    [reloadEmployee]
  );

  const logout = useCallback(async () => {
    const refreshToken = getStoredRefreshToken();
    clearSession();
    setEmployee(null);
    if (refreshToken) {
      try {
        await api.logout(refreshToken);
      } catch {
        // best-effort; the local session is already cleared
      }
    }
    router.push("/login");
  }, [router]);

  // Boot: if a refresh token exists, silently refresh before rendering
  // protected routes.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = getStoredRefreshToken();
      const tenantId = getTenantId();
      if (stored && tenantId) {
        await refreshSession();
        if (!cancelled) await reloadEmployee();
      }
      if (!cancelled) setBooted(true);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Proactive refresh scheduling: refresh a bit before the access token
  // expires so an in-progress session never hits a surprise 401.
  useEffect(() => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    if (!accessToken) return;
    const parts = accessToken.split(".");
    const payloadSegment = parts[1];
    if (parts.length < 2 || !payloadSegment) return;
    try {
      const payload = JSON.parse(atob(payloadSegment.replace(/-/g, "+").replace(/_/g, "/")));
      const expiresAt = payload.exp * 1000;
      const delay = Math.max(expiresAt - Date.now() - 60_000, 5_000);
      refreshTimer.current = setTimeout(() => {
        refreshSession();
      }, delay);
    } catch {
      // ignore malformed token
    }
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [accessToken]);

  const value = useMemo<AuthContextValue>(
    () => ({
      booted,
      isAuthenticated: !!accessToken,
      employee,
      role: employee?.roles?.includes("admin")
        ? "admin"
        : employee?.roles?.includes("manager")
        ? "manager"
        : (getRole() as Role | null),
      employeeId: getEmployeeId(),
      tenantId: getTenantId(),
      refreshingEmployee,
      loginWithTokens,
      logout,
      reloadEmployee,
    }),
    [booted, accessToken, employee, refreshingEmployee, loginWithTokens, logout, reloadEmployee]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
