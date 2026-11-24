"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CreditCard, Info, Megaphone, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  BillingCycle,
  BoostCheckoutResponse,
  BoostPackage,
  BoostPackagesOverview,
  PaymentTransaction,
  Plan,
  Product,
  SubscriptionOverview,
  UsageCounter,
} from "@/types/api";

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
            nearLimit ? "bg-red-500" : "bg-gradient-to-r from-brand-500 to-brand-700"
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

  const [cycle, setCycle] = useState<BillingCycle>("monthly");
  const [checkoutBanner, setCheckoutBanner] = useState("");
  const [checkoutError, setCheckoutError] = useState("");
  const [boostProductId, setBoostProductId] = useState("");
  const verifiedRef = useRef(false);

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

  const { data: boostOverview } = useQuery({
    queryKey: ["boost-packages", activeOrganization?.id],
    queryFn: () => apiRequest<BoostPackagesOverview>("/subscriptions/boost-packages/"),
    enabled: !!activeOrganization?.id,
  });

  const { data: myProducts } = useQuery({
    queryKey: ["boost-products", activeOrganization?.id],
    queryFn: async () => {
      const res = await apiRequest<{ results: Product[] } | Product[]>("/products/?status=published");
      const list = Array.isArray(res) ? res : res.results;
      return list.filter((p) => p.status === "published");
    },
    enabled: !!activeOrganization?.id,
  });

  const verifyMutation = useMutation({
    mutationFn: (reference: string) =>
      apiRequest<{ processed: boolean; detail: string }>("/subscriptions/verify/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({ reference }),
      }),
    onSuccess: (res) => {
      setCheckoutError("");
      setCheckoutBanner(`Payment confirmed: ${res.detail}`);
      queryClient.invalidateQueries({ queryKey: ["subscription-overview"] });
      queryClient.invalidateQueries({ queryKey: ["boost-packages"] });
    },
    onError: (err) => {
      setCheckoutBanner("");
      setCheckoutError(err instanceof Error ? err.message : "Could not verify payment.");
    },
  });

  // Verify automatically when returning from Paystack Hosted Checkout (?reference=... or ?trxref=...)
  useEffect(() => {
    if (verifiedRef.current || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("reference") || params.get("trxref");
    if (ref) {
      verifiedRef.current = true;
      verifyMutation.mutate(ref);
      window.history.replaceState({}, "", "/billing");
    }
  }, [verifyMutation]);

  function goToPaystack(tx: PaymentTransaction | null) {
    if (tx?.authorization_url && typeof window !== "undefined") {
      window.location.href = tx.authorization_url;
      return true;
    }
    return false;
  }

  const checkoutMutation = useMutation({
    mutationFn: (planCode: string) =>
      apiRequest<PaymentTransaction>("/subscriptions/checkout/", {
        method: "POST",
        body: JSON.stringify({ plan_code: planCode, billing_cycle: cycle }),
      }),
    onSuccess: (tx) => {
      queryClient.invalidateQueries({ queryKey: ["subscription-overview"] });
      setCheckoutError("");
      if (tx.status === "succeeded") {
        setCheckoutBanner(`Plan updated immediately (reference ${tx.reference}).`);
      } else if (!goToPaystack(tx)) {
        setCheckoutBanner(
          `Created pending transaction ${tx.reference} for ${formatCurrency(
            tx.amount,
            tx.currency
          )}. Your plan activates automatically once payment is verified.`
        );
      }
    },
    onError: (err) => {
      setCheckoutBanner("");
      setCheckoutError(err instanceof Error ? err.message : "Could not initiate plan change.");
    },
  });

  const boostMutation = useMutation({
    mutationFn: ({ pkg, useCredit }: { pkg: BoostPackage; useCredit: boolean }) =>
      apiRequest<BoostCheckoutResponse>("/subscriptions/boosts/checkout/", {
        method: "POST",
        body: JSON.stringify({
          boost_type: pkg.code,
          product: pkg.scope === "product" ? boostProductId || null : null,
          use_plan_credit: useCredit,
        }),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["subscription-overview"] });
      queryClient.invalidateQueries({ queryKey: ["boost-packages"] });
      setCheckoutError("");
      if (res.boost.status === "active") {
        setCheckoutBanner(res.detail);
      } else if (!goToPaystack(res.transaction)) {
        setCheckoutBanner(res.detail);
      }
    },
    onError: (err) => {
      setCheckoutBanner("");
      setCheckoutError(err instanceof Error ? err.message : "Could not create boost.");
    },
  });

  const currentPlanCode = overview?.subscription.plan.code;
  const currentCycle = overview?.subscription.billing_cycle;

  function planPrice(plan: Plan) {
    return cycle === "annual" && Number(plan.annual_price) > 0 ? plan.annual_price : plan.monthly_price;
  }

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
                Plans, Boosts &amp; Billing
              </div>
              <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
                {overview ? `${overview.subscription.plan.name} Plan` : "Billing & Plans"}
              </h1>
              {overview && (
                <p className="mt-1 text-sm text-plum-soft">
                  {formatCurrency(
                    overview.subscription.billing_cycle === "annual" &&
                      Number(overview.subscription.plan.annual_price) > 0
                      ? overview.subscription.plan.annual_price
                      : overview.subscription.plan.monthly_price,
                    overview.subscription.plan.currency
                  )}{" "}
                  / {overview.subscription.billing_cycle === "annual" ? "year" : "month"} · Status:{" "}
                  <strong className="capitalize text-white">{overview.subscription.status}</strong>
                  {overview.subscription.current_period_end
                    ? ` · Renews ${formatDateTime(overview.subscription.current_period_end)}`
                    : ""}
                  {` · Escrow fee ${overview.subscription.plan.escrow_fee_rate_pct}%`}
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
            <Card>
              <CardHeader>
                <h2 className="text-base font-bold text-plum">Live Workspace Usage</h2>
                <p className="text-xs text-ink-faint">
                  Calculated from your workspace records and enforced server-side.
                </p>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <UsageMeter label="Team Members" counter={overview.usage.members} />
                <UsageMeter label="Active Customers" counter={overview.usage.customers} />
                <UsageMeter
                  label="Monthly Measurement Links"
                  counter={overview.usage.monthly_measurement_requests}
                />
                <UsageMeter label="Catalogue Products" counter={overview.usage.products} />
                <UsageMeter label="Neighborhoods Covered" counter={overview.usage.service_wards} />
                <UsageMeter
                  label="Free Spotlight Boosts (this month)"
                  counter={overview.usage.monthly_boost_credits}
                />
              </CardContent>
            </Card>

            {/* Plan Comparison */}
            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-extrabold text-plum">Choose Your Plan</h2>
                <div className="inline-flex rounded-full border border-line bg-white p-1 shadow-mezer-sm">
                  {(["monthly", "annual"] as const).map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setCycle(c)}
                      className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-colors ${
                        cycle === c ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
                      }`}
                    >
                      {c === "monthly" ? "Monthly" : "Annual · 2 months free"}
                    </button>
                  ))}
                </div>
              </div>

              {!overview.paystack_configured && (
                <div className="mb-4 flex items-start gap-2.5 rounded-mezer-sm border border-brand-200 bg-surface-blush p-3.5 text-xs text-ink">
                  <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                  <p>
                    <strong>Payment setup pending:</strong> online checkout is not configured in this
                    environment. Selecting a paid plan creates a pending transaction that activates
                    after payment confirmation or admin assignment.
                  </p>
                </div>
              )}

              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
                {plans?.map((plan) => {
                  const isCurrent = plan.code === currentPlanCode && (
                    Number(plan.monthly_price) === 0 || currentCycle === cycle
                  );
                  return (
                    <Card
                      key={plan.id}
                      className={`flex flex-col justify-between ${
                        isCurrent
                          ? "border-brand-600 ring-2 ring-brand-600/15"
                          : plan.is_popular
                            ? "border-brand-300"
                            : ""
                      }`}
                    >
                      <CardContent className="space-y-4 p-6">
                        <div className="flex items-center justify-between gap-2">
                          <h3 className="text-lg font-extrabold text-plum">{plan.name}</h3>
                          {isCurrent ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-surface-blush px-2.5 py-0.5 text-[11px] font-bold text-brand-700">
                              <Sparkles className="h-3 w-3" /> Current
                            </span>
                          ) : plan.is_popular ? (
                            <span className="rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-bold text-white">
                              Most popular
                            </span>
                          ) : null}
                        </div>
                        <p className="text-xs leading-relaxed text-ink-soft">{plan.description}</p>
                        <div className="text-2xl font-extrabold text-plum">
                          {formatCurrency(planPrice(plan), plan.currency)}
                          <span className="text-xs font-medium text-ink-faint">
                            {Number(plan.monthly_price) === 0
                              ? " forever"
                              : cycle === "annual"
                                ? " / year"
                                : " / month"}
                          </span>
                        </div>
                        <ul className="space-y-2 pt-2 text-xs text-ink-soft">
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            Cover {plan.max_service_wards} neighborhood
                            {plan.max_service_wards === 1 ? "" : "s"}
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            {plan.escrow_fee_rate_pct}% payment-protection fee
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            {plan.monthly_free_boosts > 0
                              ? `${plan.monthly_free_boosts} free Spotlight boost / month`
                              : "Pay-as-you-go Spotlight boosts"}
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            Up to {plan.max_members} team members
                          </li>
                          <li className="flex items-center gap-2">
                            <Check className="h-3.5 w-3.5 text-brand-700" />
                            Up to {plan.max_customers} customers
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

            {/* Spotlight Boosts */}
            {boostOverview && (
              <Card>
                <CardHeader className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="flex items-center gap-2 text-base font-bold text-plum">
                      <Megaphone className="h-4 w-4 text-brand-700" /> Spotlight Boosts
                    </h2>
                    <p className="text-xs text-ink-faint">
                      Appear at the top of nearby search results and get more calls and orders.
                    </p>
                  </div>
                  <span className="rounded-full bg-surface-blush px-3 py-1 text-[11px] font-bold text-brand-700">
                    Free boosts this month: {boostOverview.monthly_credits_used} /{" "}
                    {boostOverview.monthly_credits_limit}
                  </span>
                </CardHeader>
                <CardContent className="space-y-4">
                  {boostOverview.packages.some((p) => p.scope === "product") && (
                    <div className="max-w-md">
                      <label className="text-xs font-semibold text-ink-soft" htmlFor="boost-product">
                        Item to feature (for Listing Boost)
                      </label>
                      <Select
                        id="boost-product"
                        value={boostProductId}
                        onChange={(e) => setBoostProductId(e.target.value)}
                        className="bg-white"
                      >
                        <option value="">Select a published product or service</option>
                        {myProducts?.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </Select>
                    </div>
                  )}

                  <div className="grid gap-4 md:grid-cols-3">
                    {boostOverview.packages.map((pkg) => {
                      const creditsLeft =
                        boostOverview.monthly_credits_limit - boostOverview.monthly_credits_used;
                      const canUseCredit = pkg.eligible_for_plan_credit && creditsLeft > 0;
                      const needsProduct = pkg.scope === "product" && !boostProductId;
                      return (
                        <div
                          key={pkg.code}
                          className="flex flex-col justify-between rounded-mezer-sm border border-line-soft bg-surface p-4"
                        >
                          <div>
                            <div className="flex items-center gap-1.5 text-sm font-extrabold text-plum">
                              <Zap className="h-4 w-4 text-brand-600" />
                              {pkg.name}
                            </div>
                            <p className="mt-1 text-xs text-ink-soft">{pkg.description}</p>
                            <div className="mt-2 text-xl font-extrabold text-plum">
                              {formatCurrency(pkg.amount, pkg.currency)}
                              <span className="text-xs font-medium text-ink-faint">
                                {" "}
                                / {pkg.duration_days} days
                              </span>
                            </div>
                          </div>
                          <div className="mt-3 space-y-2">
                            <Button
                              size="sm"
                              className="w-full"
                              disabled={!canManageBilling || needsProduct || boostMutation.isPending}
                              onClick={() => boostMutation.mutate({ pkg, useCredit: false })}
                            >
                              Boost for {formatCurrency(pkg.amount, pkg.currency)}
                            </Button>
                            {canUseCredit && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="w-full"
                                disabled={!canManageBilling || needsProduct || boostMutation.isPending}
                                onClick={() => boostMutation.mutate({ pkg, useCredit: true })}
                              >
                                Use free monthly boost
                              </Button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {boostOverview.active_boosts.length > 0 && (
                    <div className="space-y-2 pt-1">
                      <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
                        Active boosts
                      </div>
                      {boostOverview.active_boosts.map((b) => (
                        <div
                          key={b.id}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-xs text-emerald-900"
                        >
                          <span className="font-semibold">
                            {b.boost_type_label}
                            {b.product_name ? ` · ${b.product_name}` : ""}
                          </span>
                          <span>
                            Live until {b.ends_at ? formatDateTime(b.ends_at) : "—"}
                            {b.used_plan_credit ? " · plan credit" : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Transaction Ledger */}
            <Card className="overflow-hidden">
              <CardHeader className="flex items-center justify-between">
                <h2 className="text-base font-bold text-plum">Billing Transactions</h2>
                <span className="inline-flex items-center gap-1.5 text-xs text-ink-faint">
                  <ShieldCheck className="h-4 w-4 text-brand-700" />
                  Payments verified server-side
                </span>
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
                          {tx.purpose === "boost" ? "Spotlight Boost" : tx.plan_name || "Subscription"}{" "}
                          · {formatCurrency(tx.amount, tx.currency)} · {tx.provider}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {tx.status === "pending" && tx.authorization_url && (
                          <a href={tx.authorization_url}>
                            <Button size="sm" variant="outline">
                              Complete payment
                            </Button>
                          </a>
                        )}
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
