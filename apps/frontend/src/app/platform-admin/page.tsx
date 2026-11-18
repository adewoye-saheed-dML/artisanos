"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Search, ShieldAlert, Users } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  AuditLogItem,
  Plan,
  PlatformAdminOrgSummary,
  PlatformAdminOverview,
} from "@/types/api";

export default function PlatformAdminPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [auditReason, setAuditReason] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  const isAdmin = !!user?.is_platform_admin;

  const { data: overview } = useQuery({
    queryKey: ["platform-admin-overview"],
    queryFn: () =>
      apiRequest<PlatformAdminOverview>("/platform-admin/overview/", { skipOrgHeader: true }),
    enabled: isAdmin,
  });

  const { data: orgs } = useQuery({
    queryKey: ["platform-admin-orgs", search],
    queryFn: () => {
      const qs = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
      return apiRequest<PlatformAdminOrgSummary[]>(`/platform-admin/organizations/${qs}`, {
        skipOrgHeader: true,
      });
    },
    enabled: isAdmin,
  });

  const { data: plans } = useQuery({
    queryKey: ["subscription-plans"],
    queryFn: () => apiRequest<Plan[]>("/subscriptions/plans/", { skipOrgHeader: true }),
    enabled: isAdmin,
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["platform-admin-audit-logs"],
    queryFn: () =>
      apiRequest<AuditLogItem[]>("/platform-admin/audit-logs/", { skipOrgHeader: true }),
    enabled: isAdmin,
  });

  const toggleStatusMutation = useMutation({
    mutationFn: ({ orgId, action }: { orgId: string; action: "suspend" | "reactivate" }) =>
      apiRequest(`/platform-admin/organizations/${orgId}/${action}/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          reason: auditReason.trim() || `Platform admin ${action} action`,
        }),
      }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["platform-admin-overview"] });
      queryClient.invalidateQueries({ queryKey: ["platform-admin-orgs"] });
      queryClient.invalidateQueries({ queryKey: ["platform-admin-audit-logs"] });
      setActionError("");
      setActionSuccess(`Organization ${vars.action}d and logged in audit trail.`);
      setAuditReason("");
    },
    onError: (err) => {
      setActionSuccess("");
      setActionError(err instanceof Error ? err.message : "Action failed.");
    },
  });

  const assignPlanMutation = useMutation({
    mutationFn: ({ orgId, planCode }: { orgId: string; planCode: string }) =>
      apiRequest(`/platform-admin/organizations/${orgId}/assign-plan/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          plan_code: planCode,
          reason: auditReason.trim() || `Admin assigned plan ${planCode}`,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform-admin-orgs"] });
      queryClient.invalidateQueries({ queryKey: ["platform-admin-audit-logs"] });
      setActionError("");
      setActionSuccess("Subscription plan updated and audited.");
      setAuditReason("");
    },
    onError: (err) => {
      setActionSuccess("");
      setActionError(err instanceof Error ? err.message : "Could not assign plan.");
    },
  });

  return (
    <AppShell>
      {!isAdmin ? (
        <Card className="rounded-mezer-lg">
          <CardContent className="py-12 text-center">
            <ShieldAlert className="mx-auto h-10 w-10 text-red-600" />
            <h1 className="mt-3 text-xl font-extrabold text-plum">Platform Admin Access Only</h1>
            <p className="mt-1 text-sm text-ink-soft">
              Your account does not hold platform administrator privileges.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div>
            <div className="mezer-eyebrow">SaaS Governance</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Platform Administration
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Inspect tenant workspaces, manage subscriptions, suspend/reactivate accounts, and
              review the immutable audit trail.
            </p>
          </div>

          {overview && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardContent className="p-5">
                  <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                    Organizations
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-plum">
                    {overview.total_organizations}
                  </div>
                  <div className="text-xs text-ink-soft">
                    {overview.active_organizations} active · {overview.suspended_organizations}{" "}
                    suspended
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                    Platform Users
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-plum">
                    {overview.total_users}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                    Total Customers
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-plum">
                    {overview.total_customers}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                    Total Orders
                  </div>
                  <div className="mt-1 text-2xl font-extrabold text-plum">
                    {overview.total_orders}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {actionSuccess && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
              {actionSuccess}
            </div>
          )}
          {actionError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
              {actionError}
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-ink-faint" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search workspaces by name, slug, or email..."
                className="mt-0 rounded-full bg-white pl-10 shadow-mezer-sm"
              />
            </div>
            <Input
              value={auditReason}
              onChange={(e) => setAuditReason(e.target.value)}
              placeholder="Audit reason for next suspend / reactivate / plan change..."
              className="mt-0 rounded-full bg-white shadow-mezer-sm"
            />
          </div>

          <Card className="overflow-hidden">
            <CardHeader className="flex flex-row items-center gap-2">
              <Building2 className="h-4 w-4 text-brand-700" />
              <h2 className="text-base font-bold text-plum">Tenant Organizations</h2>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line bg-surface-blush text-[11px] font-bold uppercase tracking-wider text-ink-faint">
                  <tr>
                    <th className="px-5 py-3">Workspace</th>
                    <th className="px-5 py-3">Plan</th>
                    <th className="px-5 py-3">Usage</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Governance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft">
                  {orgs?.map((o) => (
                    <tr key={o.id}>
                      <td className="px-5 py-3.5">
                        <div className="font-bold text-plum">{o.name}</div>
                        <div className="text-xs text-ink-faint">
                          /{o.slug} · <span className="capitalize">{o.category}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <Select
                          aria-label={`Plan for ${o.name}`}
                          value={o.plan_code}
                          className="mt-0 max-w-[150px] py-1 text-xs"
                          onChange={(e) =>
                            assignPlanMutation.mutate({ orgId: o.id, planCode: e.target.value })
                          }
                        >
                          {plans?.map((p) => (
                            <option key={p.code} value={p.code}>
                              {p.name}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-ink-soft">
                        <span className="inline-flex items-center gap-1">
                          <Users className="h-3.5 w-3.5" /> {o.member_count}m · {o.customer_count}c
                          · {o.order_count}o
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <StatusBadge status={o.is_active ? "active" : "suspended"} />
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <Button
                          size="sm"
                          variant={o.is_active ? "danger" : "secondary"}
                          onClick={() =>
                            toggleStatusMutation.mutate({
                              orgId: o.id,
                              action: o.is_active ? "suspend" : "reactivate",
                            })
                          }
                        >
                          {o.is_active ? "Suspend" : "Reactivate"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <h2 className="text-base font-bold text-plum">Audit Trail</h2>
            </CardHeader>
            <CardContent className="divide-y divide-line-soft p-0">
              {!auditLogs?.length ? (
                <p className="p-6 text-sm text-ink-faint">No audit events recorded yet.</p>
              ) : (
                auditLogs.map((log) => (
                  <div
                    key={log.id}
                    className="flex flex-wrap items-center justify-between gap-2 px-6 py-3.5 text-xs"
                  >
                    <div>
                      <span className="font-extrabold uppercase text-brand-700">{log.action}</span>
                      {log.organization_name && (
                        <span className="font-semibold text-plum"> · {log.organization_name}</span>
                      )}
                      {log.reason && <span className="text-ink-soft"> — {log.reason}</span>}
                    </div>
                    <div className="text-ink-faint">
                      {log.actor_email || "system"} · {formatDateTime(log.created_at)}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </AppShell>
  );
}
