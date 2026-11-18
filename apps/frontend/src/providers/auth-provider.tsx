"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

import { apiRequest, getActiveOrganizationId, setActiveOrganizationId } from "@/lib/api-client";
import type { MembershipSummary, Organization, User } from "@/types/api";

interface AuthContextValue {
  user: User | null;
  activeMembership: MembershipSummary | null;
  activeOrganization: Organization | null;
  isLoading: boolean;
  refreshUser: () => Promise<User | null>;
  switchOrganization: (orgId: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [activeOrgId, setActiveOrgIdState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const pickActiveOrg = useCallback((loadedUser: User | null) => {
    if (!loadedUser || loadedUser.memberships.length === 0) {
      setActiveOrganizationId(null);
      setActiveOrgIdState(null);
      return;
    }
    const stored = getActiveOrganizationId();
    const validMatch = loadedUser.memberships.find((m) => m.organization.id === stored);
    const chosen = validMatch ? validMatch.organization.id : loadedUser.memberships[0].organization.id;
    setActiveOrganizationId(chosen);
    setActiveOrgIdState(chosen);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const res = await apiRequest<{ user: User }>("/auth/me/", { skipOrgHeader: true });
      setUser(res.user);
      pickActiveOrg(res.user);
      return res.user;
    } catch {
      setUser(null);
      setActiveOrganizationId(null);
      setActiveOrgIdState(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [pickActiveOrg]);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const switchOrganization = useCallback(
    (orgId: string) => {
      setActiveOrganizationId(orgId);
      setActiveOrgIdState(orgId);
      queryClient.invalidateQueries();
    },
    [queryClient]
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest("/auth/logout/", { method: "POST", body: JSON.stringify({}), skipOrgHeader: true });
    } finally {
      setUser(null);
      setActiveOrganizationId(null);
      setActiveOrgIdState(null);
      queryClient.clear();
    }
  }, [queryClient]);

  const activeMembership =
    user?.memberships.find((m) => m.organization.id === activeOrgId) || user?.memberships[0] || null;
  const activeOrganization = activeMembership?.organization || null;

  return (
    <AuthContext.Provider
      value={{
        user,
        activeMembership,
        activeOrganization,
        isLoading,
        refreshUser,
        switchOrganization,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
