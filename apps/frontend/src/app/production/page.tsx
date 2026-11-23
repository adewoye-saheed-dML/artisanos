"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardList, Kanban, User } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiRequest } from "@/lib/api-client";
import { formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { OrderStatus, ProductionBoardResponse } from "@/types/api";

const NEXT_STAGE_PREFERRED: Partial<Record<OrderStatus, OrderStatus>> = {
  confirmed: "in_production",
  in_production: "fitting",
  fitting: "ready",
  ready: "completed",
};

export default function ProductionBoardPage() {
  const { activeOrganization } = useAuth();
  const queryClient = useQueryClient();
  const [boardError, setBoardError] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["production-board", activeOrganization?.id],
    queryFn: () => apiRequest<ProductionBoardResponse>("/production/board/"),
    enabled: !!activeOrganization?.id,
  });

  const transitionMutation = useMutation({
    mutationFn: ({ orderId, toStatus }: { orderId: string; toStatus: OrderStatus }) =>
      apiRequest(`/orders/${orderId}/transition/`, {
        method: "POST",
        body: JSON.stringify({
          to_status: toStatus,
          notes: `Moved on production board to ${formatStatusLabel(toStatus)}`,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["production-board"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      setBoardError("");
    },
    onError: (err) => {
      setBoardError(err instanceof Error ? err.message : "Could not move order.");
    },
  });

  const totalBoardOrders =
    data?.columns.reduce((acc, col) => acc + col.orders.length, 0) ?? 0;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Workshop Floor</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Production Board
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Track confirmed garments through cutting, sewing, fitting, and final quality checks.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <Link href="/appointments" className="w-full sm:w-auto">
              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                Fittings calendar
              </Button>
            </Link>
            <Link href="/orders" className="w-full sm:w-auto">
              <Button size="sm" className="w-full sm:w-auto">
                <ClipboardList className="h-4 w-4" />
                All orders
              </Button>
            </Link>
          </div>
        </div>

        {boardError && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {boardError}
          </div>
        )}

        {error && (
          <div className="rounded-mezer-sm border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Could not load production board: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {isLoading && (
          <div className="grid gap-4 lg:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="h-64 animate-pulse bg-white/70" />
            ))}
          </div>
        )}

        {data && totalBoardOrders === 0 && (
          <Card className="border-dashed border-brand-200 bg-surface-blush">
            <CardContent className="py-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-white text-brand-700 shadow-mezer-sm">
                <Kanban className="h-6 w-6" />
              </div>
              <h2 className="mt-3 text-lg font-bold text-plum">No garments in production yet</h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-ink-soft">
                Once an order reaches <strong>Confirmed</strong> status, it appears automatically on
                this Kanban board with its task checklist progress.
              </p>
              <Link href="/orders" className="mt-5 inline-block">
                <Button>Open tailoring orders</Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {data && totalBoardOrders > 0 && (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {data.columns.map((col) => (
              <div
                key={col.status}
                className="flex flex-col rounded-mezer-md border border-line bg-white/75 p-4 shadow-mezer-sm"
              >
                <div className="mb-4 flex items-center justify-between border-b border-line-soft pb-3">
                  <h2 className="text-sm font-extrabold tracking-tight text-plum">{col.label}</h2>
                  <span className="flex h-6 min-w-6 items-center justify-center rounded-full bg-surface-blush px-2 text-xs font-bold text-brand-700">
                    {col.orders.length}
                  </span>
                </div>

                <div className="space-y-3">
                  {col.orders.length === 0 ? (
                    <div className="rounded-mezer-sm border border-dashed border-line py-8 text-center text-xs text-ink-faint">
                      No orders in {col.label.toLowerCase()}
                    </div>
                  ) : (
                    col.orders.map((ord) => {
                      const pct =
                        ord.total_tasks > 0
                          ? Math.round((ord.completed_tasks / ord.total_tasks) * 100)
                          : 0;
                      const primaryNext = NEXT_STAGE_PREFERRED[ord.status];
                      const canMovePrimary =
                        primaryNext && ord.allowed_next_statuses.includes(primaryNext);

                      return (
                        <div
                          key={ord.id}
                          className="rounded-mezer-sm border border-line bg-white p-4 shadow-mezer-sm transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-card"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <Link
                              href={`/orders/${ord.id}`}
                              className="text-xs font-extrabold uppercase tracking-wider text-brand-700 hover:underline"
                            >
                              {ord.order_number}
                            </Link>
                            {ord.alteration_tasks > 0 && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                                <AlertTriangle className="h-3 w-3" />
                                {ord.alteration_tasks} alt
                              </span>
                            )}
                          </div>

                          <Link
                            href={`/orders/${ord.id}`}
                            className="mt-1 block text-sm font-bold text-plum hover:text-brand-700"
                          >
                            {ord.garment_type}
                          </Link>
                          <div className="mt-0.5 text-xs text-ink-soft">{ord.customer_name}</div>

                          {/* Task progress */}
                          <div className="mt-3">
                            <div className="flex items-center justify-between text-[11px] font-medium text-ink-faint">
                              <span>Checklist</span>
                              <span>
                                {ord.completed_tasks}/{ord.total_tasks}
                              </span>
                            </div>
                            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-700 transition-all"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>

                          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-faint">
                            <span className="inline-flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {ord.assigned_to_name || "Unassigned"}
                            </span>
                            {ord.expected_completion_date && (
                              <span>Due {ord.expected_completion_date}</span>
                            )}
                          </div>

                          <div className="mt-3.5 flex items-center justify-between gap-2 border-t border-line-soft pt-3">
                            <Link
                              href={`/orders/${ord.id}`}
                              className="text-xs font-semibold text-ink-soft hover:text-brand-700"
                            >
                              Checklist
                            </Link>
                            {canMovePrimary && primaryNext && (
                              <Button
                                size="sm"
                                variant={primaryNext === "completed" ? "secondary" : "primary"}
                                className="h-7 px-3 text-[11px]"
                                disabled={transitionMutation.isPending}
                                onClick={() =>
                                  transitionMutation.mutate({
                                    orderId: ord.id,
                                    toStatus: primaryNext,
                                  })
                                }
                              >
                                {primaryNext === "completed" ? (
                                  <>
                                    <CheckCircle2 className="h-3 w-3" /> Complete
                                  </>
                                ) : (
                                  <>
                                    {formatStatusLabel(primaryNext)}
                                    <ArrowRight className="h-3 w-3" />
                                  </>
                                )}
                              </Button>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
