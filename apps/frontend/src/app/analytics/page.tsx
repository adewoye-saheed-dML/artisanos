"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, ListChecks, Ruler, TrendingUp } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { AnalyticsOverview } from "@/types/api";

export default function AnalyticsPage() {
  const { activeOrganization, activeMembership } = useAuth();
  const [months, setMonths] = useState("6");
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState<string | null>(null);

  const canExport = activeMembership?.role === "owner" || activeMembership?.role === "manager";

  const { data, isLoading, error } = useQuery({
    queryKey: ["analytics-overview", activeOrganization?.id, months],
    queryFn: () => apiRequest<AnalyticsOverview>(`/analytics/overview/?months=${months}`),
    enabled: !!activeOrganization?.id,
  });

  async function downloadCsv(kind: "customers" | "orders") {
    if (!activeOrganization?.id) return;
    setExportError("");
    setExporting(kind);
    try {
      const res = await fetch(`/api/v1/analytics/export/${kind}/`, {
        method: "GET",
        credentials: "include",
        headers: { "X-Organization-Id": activeOrganization.id },
      });
      if (!res.ok) {
        throw new Error(`Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeOrganization.slug}-${kind}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Could not export CSV.");
    } finally {
      setExporting(null);
    }
  }

  const maxQuoted = Math.max(
    1,
    ...(data?.monthly_revenue_trend.map((m) => parseFloat(m.quoted_total) || 0) || [1])
  );

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Business Intelligence</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Analytics &amp; Reports
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Real PostgreSQL aggregates for revenue, orders, production efficiency, and
              measurements.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
            <Select
              aria-label="Date range months"
              value={months}
              onChange={(e) => setMonths(e.target.value)}
              className="col-span-2 mt-0 w-full rounded-full bg-white py-2 text-xs shadow-mezer-sm sm:col-span-1 sm:w-36"
            >
              <option value="3">Last 3 months</option>
              <option value="6">Last 6 months</option>
              <option value="12">Last 12 months</option>
            </Select>
            {canExport && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full sm:w-auto"
                  disabled={exporting !== null}
                  onClick={() => void downloadCsv("customers")}
                >
                  <Download className="h-3.5 w-3.5" />
                  {exporting === "customers" ? "Exporting..." : "Customers CSV"}
                </Button>
                <Button
                  size="sm"
                  className="w-full sm:w-auto"
                  disabled={exporting !== null}
                  onClick={() => void downloadCsv("orders")}
                >
                  <Download className="h-3.5 w-3.5" />
                  {exporting === "orders" ? "Exporting..." : "Orders CSV"}
                </Button>
              </>
            )}
          </div>
        </div>

        {exportError && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
            {exportError}
          </div>
        )}

        {error && (
          <div className="rounded-mezer-sm border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Could not load analytics: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {isLoading && <Card className="h-56 animate-pulse bg-white/70" />}

        {data && (
          <>
            {/* Operational KPI Cards */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-ink-faint">
                    <span>Task Completion</span>
                    <ListChecks className="h-4 w-4 text-brand-700" />
                  </div>
                  <div className="mt-2 text-2xl font-extrabold text-plum">
                    {data.production.completion_rate_pct}%
                  </div>
                  <div className="mt-0.5 text-xs text-ink-soft">
                    {data.production.completed_tasks} of {data.production.total_tasks} tasks done
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                    Open Alterations
                  </div>
                  <div className="mt-2 text-2xl font-extrabold text-plum">
                    {data.production.open_alterations}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-soft">Flagged adjustment items</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-ink-faint">
                    <span>Verified Fit Profiles</span>
                    <Ruler className="h-4 w-4 text-brand-700" />
                  </div>
                  <div className="mt-2 text-2xl font-extrabold text-plum">
                    {data.measurements.verified_profiles} / {data.measurements.total_profiles}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-soft">
                    {data.measurements.customer_submitted_profiles} client-submitted ·{" "}
                    {data.measurements.imported_profiles} imported
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-5">
                  <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                    Active Fit Passports
                  </div>
                  <div className="mt-2 text-2xl font-extrabold text-plum">
                    {data.measurements.active_share_links}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-soft">Consented portable share links</div>
                </CardContent>
              </Card>
            </div>

            {/* Monthly Revenue & Deposit Trend */}
            <Card>
              <CardHeader className="flex flex-row items-center gap-2">
                <TrendingUp className="h-4 w-4 text-brand-700" />
                <div>
                  <h2 className="text-base font-bold text-plum">
                    Monthly Quoted Value &amp; Deposits Collected
                  </h2>
                  <p className="text-xs text-ink-faint">
                    Excludes cancelled orders · Currency: {data.currency}
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                {data.monthly_revenue_trend.length === 0 ? (
                  <p className="py-6 text-center text-sm text-ink-faint">
                    No non-cancelled order activity recorded in the selected window yet.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {data.monthly_revenue_trend.map((pt) => {
                      const quoted = parseFloat(pt.quoted_total) || 0;
                      const deposits = parseFloat(pt.deposits_collected) || 0;
                      const quotedPct = Math.max(4, Math.round((quoted / maxQuoted) * 100));
                      const depositPct = quoted > 0 ? Math.min(100, Math.round((deposits / quoted) * 100)) : 0;
                      return (
                        <div key={pt.month} className="space-y-1.5">
                          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                            <span className="font-bold text-plum">
                              {pt.month}{" "}
                              <span className="font-normal text-ink-faint">
                                ({pt.orders_count} {pt.orders_count === 1 ? "order" : "orders"})
                              </span>
                            </span>
                            <span className="text-ink-soft">
                              Quoted: <strong>{formatCurrency(pt.quoted_total, data.currency)}</strong>{" "}
                              · Deposits:{" "}
                              <strong className="text-brand-700">
                                {formatCurrency(pt.deposits_collected, data.currency)}
                              </strong>
                            </span>
                          </div>
                          <div className="h-3 overflow-hidden rounded-full bg-surface">
                            <div
                              className="relative h-full rounded-full bg-brand-200"
                              style={{ width: `${quotedPct}%` }}
                            >
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-700"
                                style={{ width: `${depositPct}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* Order Status Funnel */}
              <Card>
                <CardHeader className="flex flex-row items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-brand-700" />
                  <h2 className="text-base font-bold text-plum">Order Pipeline Breakdown</h2>
                </CardHeader>
                <CardContent className="divide-y divide-line-soft p-0">
                  {data.order_status_breakdown.length === 0 ? (
                    <p className="p-6 text-sm text-ink-faint">No orders recorded yet.</p>
                  ) : (
                    data.order_status_breakdown.map((row) => (
                      <div
                        key={row.status}
                        className="flex items-center justify-between px-6 py-3.5"
                      >
                        <StatusBadge status={row.status} />
                        <span className="text-sm font-extrabold text-plum">{row.count}</span>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              {/* Top Garments */}
              <Card>
                <CardHeader>
                  <h2 className="text-base font-bold text-plum">Top Requested Garments / Items</h2>
                </CardHeader>
                <CardContent className="divide-y divide-line-soft p-0">
                  {data.top_garment_types.length === 0 ? (
                    <p className="p-6 text-sm text-ink-faint">No active orders yet.</p>
                  ) : (
                    data.top_garment_types.map((g) => (
                      <div
                        key={g.garment_type}
                        className="flex items-center justify-between gap-3 px-4 py-3.5 sm:px-6"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm font-bold text-plum">{g.garment_type}</div>
                          <div className="text-xs text-ink-faint">
                            {g.count} {g.count === 1 ? "order" : "orders"}
                          </div>
                        </div>
                        <span className="shrink-0 text-sm font-bold text-brand-700">
                          {formatCurrency(g.quoted_total, data.currency)}
                        </span>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
