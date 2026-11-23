"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Calendar,
  ClipboardList,
  PackageCheck,
  Ruler,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { DashboardSummary } from "@/types/api";

export default function DashboardPage() {
  const { activeOrganization } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-summary", activeOrganization?.id],
    queryFn: () => apiRequest<DashboardSummary>("/dashboard/summary/"),
    enabled: !!activeOrganization?.id,
  });

  const currency = data?.organization.currency || activeOrganization?.currency || "NGN";

  return (
    <AppShell>
      <div className="space-y-7">
        {/* Velvet Plum Workspace Banner */}
        <div className="relative overflow-hidden rounded-mezer-lg bg-plum px-6 py-7 text-white shadow-card sm:px-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-brand-500/20 blur-3xl"
          />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="mezer-eyebrow-light">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                Workspace Overview
              </div>
              <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
                {activeOrganization?.name}
              </h1>
              <p className="mt-1 text-sm text-plum-soft">
                Real-time customer records, measurement profiles, and tailoring orders.
              </p>
            </div>
            <div className="flex flex-wrap gap-2.5">
              <Link href="/customers">
                <Button variant="light" size="sm">
                  <Users className="h-4 w-4" />
                  Add customer
                </Button>
              </Link>
              <Link href="/orders">
                <Button size="sm">
                  <ClipboardList className="h-4 w-4" />
                  New order
                </Button>
              </Link>
            </div>
          </div>
        </div>

        {isLoading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Card key={i} className="h-28 animate-pulse bg-white/70" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-mezer-sm border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Could not load dashboard metrics: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {data && (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <MetricCard
                label="Total Customers"
                value={String(data.metrics.total_customers)}
                icon={Users}
              />
              <MetricCard
                label="Active Orders"
                value={String(data.metrics.active_orders)}
                icon={ClipboardList}
              />
              <MetricCard
                label="Awaiting Measurements"
                value={String(data.metrics.orders_awaiting_measurements)}
                icon={Ruler}
              />
              <MetricCard
                label="In Production / Fitting"
                value={String(data.metrics.orders_in_production)}
                icon={ClipboardList}
              />
              <MetricCard
                label="Ready for Collection"
                value={String(data.metrics.orders_ready)}
                icon={PackageCheck}
              />
              <MetricCard
                label="Upcoming Fittings"
                value={String(data.metrics.upcoming_appointments)}
                icon={Calendar}
              />
              <MetricCard
                label="Monthly Recorded Deposits"
                value={formatCurrency(data.metrics.monthly_recorded_deposits, currency)}
                icon={Wallet}
              />
            </div>

            {data.upcoming_appointments.length > 0 && (
              <Card className="overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-brand-700" />
                    <h2 className="text-base font-bold text-plum">Upcoming Fittings &amp; Appointments</h2>
                  </div>
                  <Link
                    href="/appointments"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline"
                  >
                    Open calendar <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </CardHeader>
                <CardContent className="divide-y divide-line-soft p-0">
                  {data.upcoming_appointments.map((appt) => (
                    <div
                      key={appt.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-6 py-3.5"
                    >
                      <div>
                        <div className="text-sm font-semibold text-plum">
                          {appt.title} · {appt.customer_name}
                        </div>
                        <div className="text-xs text-ink-soft">
                          {formatDateTime(appt.scheduled_at)} · {appt.location}
                        </div>
                      </div>
                      <StatusBadge status={appt.status} />
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {data.metrics.total_customers === 0 && data.metrics.active_orders === 0 ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <div className="mezer-eyebrow justify-center">Get Started</div>
                  <h2 className="mt-2 text-xl font-bold text-plum">Your workshop is ready</h2>
                  <p className="mx-auto mt-1.5 max-w-md text-sm text-ink-soft">
                    Start by adding your first customer, recording their measurements, and creating a tailoring order.
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-3">
                    <Link href="/customers">
                      <Button>Add your first customer</Button>
                    </Link>
                    <Link href="/templates">
                      <Button variant="outline">Review measurement templates</Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 lg:grid-cols-2">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <h2 className="text-base font-bold text-plum">Recent Orders</h2>
                    <Link
                      href="/orders"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline"
                    >
                      View all <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </CardHeader>
                  <CardContent className="divide-y divide-line-soft p-0">
                    {data.recent_orders.length === 0 ? (
                      <p className="p-4 text-sm text-ink-faint sm:p-6">No orders recorded yet.</p>
                    ) : (
                      data.recent_orders.map((order) => (
                        <Link
                          key={order.id}
                          href={`/orders/${order.id}`}
                          className="flex items-center justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-surface-blush sm:px-6 sm:py-4"
                        >
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-plum">
                              {order.order_number} · {order.garment_type}
                            </div>
                            <div className="mt-0.5 truncate text-xs text-ink-soft">
                              {order.customer_name} · {formatCurrency(order.quoted_amount, order.currency)}
                            </div>
                          </div>
                          <StatusBadge status={order.status} className="shrink-0" />
                        </Link>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <h2 className="text-base font-bold text-plum">Recent Customers</h2>
                    <Link
                      href="/customers"
                      className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline"
                    >
                      View all <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </CardHeader>
                  <CardContent className="divide-y divide-line-soft p-0">
                    {data.recent_customers.length === 0 ? (
                      <p className="p-4 text-sm text-ink-faint sm:p-6">No customers added yet.</p>
                    ) : (
                      data.recent_customers.map((customer) => (
                        <Link
                          key={customer.id}
                          href={`/customers/${customer.id}`}
                          className="flex items-center justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-surface-blush sm:px-6 sm:py-4"
                        >
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-plum">
                              {customer.full_name}
                            </div>
                            <div className="mt-0.5 truncate text-xs text-ink-soft">{customer.phone}</div>
                          </div>
                          <div className="shrink-0 text-xs text-ink-faint">
                            {formatDateTime(customer.created_at)}
                          </div>
                        </Link>
                      ))
                    )}
                  </CardContent>
                </Card>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Card className="transition-all duration-150 hover:-translate-y-0.5 hover:shadow-card-hover">
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wider text-ink-faint">{label}</p>
          <p className="mt-1.5 text-2xl font-extrabold tracking-tight text-plum">{value}</p>
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-blush text-brand-700 ring-1 ring-brand-200/70">
          <Icon className="h-5 w-5" />
        </div>
      </CardContent>
    </Card>
  );
}
