"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CreditCard, Info, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { PaymentTransaction, Plan, SubscriptionOverview, UsageCounter } from "@/types/api";

function UsageMeter({ label, counter }: { label: string; counter: UsageCounter }) {
  const pct = counter.limit > 0 ? Math.min(100, Math.round((counter.used / counter.limit) * 100)) : 0;
  const nearLimit = pct >= 80;
  return (
    <div className="rounded-mezer-sm border border-line-soft bg-surface-blush p-4">
      <div className="flex items-center justify-between text-xs font-semibold">
        <span className="text-ink-soft">{label}</span>
        <span className={nearLimit ? "font-bold text-red-700" : "font-bold text-plum"}>
          {counter.used} / {counter.limit}
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
        <div
          className={`h-full rounded-full transition-all ${
            nearLimit
              ? "bg-red-500"
              : "bg-gradient-to-r from-brand-500 to-brand-700"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function BillingPage() {
  const { activeOrganization, activeMembership } = useAuth();
  const queryClient = useQueryClient();
  const canManageBilling =
    activeMembership?.role === "owner" || activeMembership?.role === "manager";

  const [checkoutBanner, setCheckoutBanner] = useState("");
  const [checkoutError, setCheckoutError] = useState("");

  const { data: overview, isLoading } = useQuery({
    queryKey: ["subscription-overview", activeOrganization?.id],
    queryFn: () => apiRequest<SubscriptionOverview>("/subscriptions/overview/"),
    enabled: !!activeOrganization?.id,
  });

  const { data: plans } = useQuery({
    queryKey: ["subscription-plans"],
    queryFn: () => apiRequest<Plan[]>("/subscriptions/plans/", { skipOrgHeader: true }),
    enabled: !!activeOrganization?.id,
  });

  const checkoutMutation = useMutation({
    mutationFn: (planCode: string) =>
      apiRequest<PaymentTransaction>("/subscriptions/checkout/", {
        method: "POST",
        body: JSON.stringify({ plan_code: planCode }),
      }),
    onSuccess: (tx) => {
      queryClient.invalidateQueries({ queryKey: ["subscription-overview"] });
      setCheckoutError("");
      if (tx.status === "succeeded") {
        setCheckoutBanner(`Plan updated immediately (reference ${tx.reference}).`);
      } else {
        setCheckoutBanner(
          `Created pending Paystack transaction ${tx.reference} for ${formatCurrency(
            tx.amount,
            tx.currency
          )}. Subscription activates automatically once verified by Paystack webhook.`
        );
      }
    },
    onError: (err) => {
      setCheckoutBanner("");
      setCheckoutError(err instanceof Error ? err.message : "Could not initiate plan change.");
    },
  });

  const currentPlanCode = overview?.subscription.plan.code;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="relative overflow-hidden rounded-mezer-lg bg-plum px-6 py-7 text-white shadow-card sm:px-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full bg-brand-500/25 blur-3xl"
          />
          <div className="relative flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="mezer-eyebrow-light">
                <CreditCard className="h-3.5 w-3.5 text-brand-300" />
                Subscription &amp; Entitlements
              </div>
              <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
                {overview ? `${overview.subscription.plan.name} Plan` : "Billing & Plans"}
              </h1>
              {overview && (
                <p className="mt-1 text-sm text-plum-soft">
                  {formatCurrency(
                    overview.subscription.plan.monthly_price,
                    overview.subscription.plan.currency
                  )}{" "}
                  / month · Status:{" "}
                  <strong className="capitalize text-white">{overview.subscription.status}</strong>
                  {overview.subscription.current_period_end
                    ? ` · Renews ${formatDateTime(overview.subscription.current_period_end)}`
                    : ""}
                </p>
              )}
            </div>
            {overview && <StatusBadge status={overview.subscription.status} />}
          </div>
        </div>

        {checkoutBanner && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {checkoutBanner}
          </div>
        )}
        {checkoutError && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {checkoutError}
          </div>
        )}

        {isLoading && <Card className="h-44 animate-pulse bg-white/70" />}

        {overview && (
          <>
            {/* Real Usage Meters */}
            <Card>
              <CardHeader>
                <h2 className="text-base font-bold text-plum">Live Workspace Usage</h2>
                <p className="text-xs text-ink-faint">
                  Calculated directly from your PostgreSQL workspace records and enforced server-side.
                </p>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <UsageMeter label="Team Members" counter={overview.usage.members} />
                <UsageMeter label="Active Customers" counter={overview.usage.customers} />
                <UsageMeter
                  label="Monthly Measurement Links"
                  counter={overview.usage.monthly_measurement_requests}
                />
                <UsageMeter label="Catalogue Products" counter={overview.usage.products} />
              </CardContent>
            </Card>

            {/* Plan Comparison */}
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-extrabold text-plum">Available Plans</h2>
                <span className="inline-flex items-center gap-1.5 text-xs text-ink-faint">
                  <ShieldCheck className="h-4 w-4 text-brand-700" />
                  Webhook-verified Paystack billing
                </span>
              </div>

              {!overview.paystack_configured && (
                <div className="mb-4 flex items-start gap-2.5 rounded-mezer-sm border border-brand-200 bg-surface-blush p-3.5 text-xs text-ink">
                  <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                  <p>
                    <strong>Paystack Webhook Mode:</strong> `PAYSTACK_SECRET_KEY` is not configured
                    in this local environment. Selecting a paid plan creates a verifiable `pending`
                    transaction that activates only after a signed `X-Paystack-Signature` webhook or
                    platform admin assignment.
                  </p>
                </div>
              )}

              <div className="grid gap-5 md:grid-cols-3">
                {plans?.map((plan) => {
                  const isCurrent = plan.code === currentPlanCode;
                  return (
                    <Card
                      key={plan.id}
                      className={`flex flex-col justify-between ${
                        isCurrent ? "border-brand-600 ring-2 ring-brand-600/15" : ""
                      }`}
                    >
                      <CardContent className="space-y-4 p-6">
                        <div className="flex items-center justify-between">
                          <h3 className="text-lg font-extrabold text-plum">{plan.name}</h3>
                          {isCurrent && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-surface-blush px-2.5 py-0.5 text-[11px] font-bold text-brand-700">
                              <Sparkles className="h-3 w-3" /> Current
                            </span>
                          )}
                        </div>
                        <p className="text-xs leading-relaxed text-ink-soft">{plan.description}</p>
                        <div className="text-2xl font-extrabold text-plum">
                          {formatCurrency(plan.monthly_price, plan.currency)}
                          <span className="text-xs font-medium text-ink-faint"> / month</span>
                        </div>
                        <ul className="space-y-2 pt-2 text-xs text-ink-soft">
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            Up to {plan.max_members} active team members
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            Up to {plan.max_customers} customers
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            {plan.max_monthly_measurement_requests} measurement links / month
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            Up to {plan.max_products} storefront products
                          </li>
                        </ul>
                      </CardContent>
                      <div className="border-t border-line-soft px-6 py-4">
                        <Button
                          size="sm"
                          variant={isCurrent ? "outline" : "primary"}
                          className="w-full"
                          disabled={isCurrent || !canManageBilling || checkoutMutation.isPending}
                          onClick={() => checkoutMutation.mutate(plan.code)}
                        >
                          {isCurrent
                            ? "Current plan"
                            : !canManageBilling
                            ? "Owner / Manager only"
                            : `Select ${plan.name}`}
                        </Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* Transaction Ledger */}
            <Card className="overflow-hidden">
              <CardHeader>
                <h2 className="text-base font-bold text-plum">Billing Transactions</h2>
              </CardHeader>
              <CardContent className="divide-y divide-line-soft p-0">
                {overview.transactions.length === 0 ? (
                  <p className="p-6 text-sm text-ink-faint">No billing transactions recorded yet.</p>
                ) : (
                  overview.transactions.map((tx) => (
                    <div
                      key={tx.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
                    >
                      <div>
                        <div className="font-mono text-xs font-bold text-plum">{tx.reference}</div>
                        <div className="text-xs text-ink-soft">
                          {tx.plan_name || "Subscription"} ·{" "}
                          {formatCurrency(tx.amount, tx.currency)} · {tx.provider}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-ink-faint">
                          {formatDateTime(tx.verified_at || tx.created_at)}
                        </span>
                        <StatusBadge status={tx.status} />
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </AppShell>
  );
}
