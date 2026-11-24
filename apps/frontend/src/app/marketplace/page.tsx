"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BadgeCheck,
  Briefcase,
  CheckCircle2,
  Lock,
  MapPin,
  MessageCircle,
  Navigation,
  Phone,
  Search,
  ShoppingBag,
  Store,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import {
  NigeriaLocationPicker,
  type NigeriaLocationValue,
} from "@/components/locations/nigeria-location-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import {
  ARTISAN_CATEGORIES,
  buildTelHref,
  buildWhatsAppHref,
  getAvailabilityBadge,
  getProximityBadgeClasses,
} from "@/lib/artisans";
import { formatCurrency, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  InquiryUrgency,
  MarketplaceCategoryCount,
  MarketplaceProductCard,
  MarketplaceStorefrontCard,
} from "@/types/api";

function MarketplaceContent() {
  const searchParams = useSearchParams();
  const { user, activeOrganization } = useAuth();
  const didHydrateProfileLocation = useRef(false);

  const initialTab =
    searchParams.get("tab") === "goods"
      ? "goods"
      : searchParams.get("tab") === "services"
        ? "services"
        : "artisans";

  const [tab, setTab] = useState<"artisans" | "goods" | "services">(initialTab);
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [category, setCategory] = useState(searchParams.get("category") || "");
  const [location, setLocation] = useState<NigeriaLocationValue>({
    stateId: searchParams.get("state") || "",
    lgaId: searchParams.get("lga") || "",
    wardId: searchParams.get("ward") || "",
    pollingUnitId: searchParams.get("polling_unit") || "",
  });
  const [exactOnly, setExactOnly] = useState(searchParams.get("exact") === "true");
  const [availableOnly, setAvailableOnly] = useState(searchParams.get("available_only") === "true");
  const [calloutOnly, setCalloutOnly] = useState(searchParams.get("callout_only") === "true");

  // Auto-populate the signed-in user's Ward & Polling Unit so nearby artisans immediately spring up
  useEffect(() => {
    if (didHydrateProfileLocation.current) return;
    const hasUrlLocation = !!(
      searchParams.get("state") ||
      searchParams.get("lga") ||
      searchParams.get("ward") ||
      searchParams.get("polling_unit")
    );
    if (hasUrlLocation) {
      didHydrateProfileLocation.current = true;
      return;
    }
    const srcState = user?.state || activeOrganization?.state || "";
    const srcLga = user?.lga || activeOrganization?.lga || "";
    const srcWard = user?.ward || activeOrganization?.ward || "";
    const srcPu = user?.polling_unit || activeOrganization?.polling_unit || "";
    if (srcState || srcLga || srcWard || srcPu) {
      didHydrateProfileLocation.current = true;
      setLocation({
        stateId: srcState,
        lgaId: srcLga,
        wardId: srcWard,
        pollingUnitId: srcPu,
      });
    }
  }, [activeOrganization, searchParams, user]);

  // Quick inline Call-for-Work modal state
  const [calloutTarget, setCalloutTarget] = useState<MarketplaceStorefrontCard | null>(null);
  const [buyerName, setBuyerName] = useState("");
  const [buyerPhone, setBuyerPhone] = useState("");
  const [urgency, setUrgency] = useState<InquiryUrgency>("today");
  const [customerAddress, setCustomerAddress] = useState("");
  const [budgetAmount, setBudgetAmount] = useState("");
  const [calloutMessage, setCalloutMessage] = useState("");
  const [calloutError, setCalloutError] = useState("");
  const [calloutSuccess, setCalloutSuccess] = useState(false);

  const buildLocationQuery = () => {
    const params = new URLSearchParams();
    if (search.trim()) params.set("search", search.trim());
    if (category) params.set("category", category);
    if (location.stateId) params.set("state", location.stateId);
    if (location.lgaId) params.set("lga", location.lgaId);
    if (location.wardId) params.set("ward", location.wardId);
    if (location.pollingUnitId) params.set("polling_unit", location.pollingUnitId);
    if (exactOnly) params.set("exact", "true");
    return params;
  };

  const { data: categoryCounts } = useQuery({
    queryKey: ["marketplace-categories"],
    queryFn: () =>
      apiRequest<MarketplaceCategoryCount[]>("/marketplace/categories/", { skipOrgHeader: true }),
    staleTime: 1000 * 60 * 5,
  });

  const { data: artisans, isLoading: loadingArtisans } = useQuery({
    queryKey: [
      "marketplace-artisans",
      search,
      category,
      location,
      exactOnly,
      availableOnly,
      calloutOnly,
    ],
    queryFn: () => {
      const params = buildLocationQuery();
      if (availableOnly) params.set("available_only", "true");
      if (calloutOnly) params.set("callout_only", "true");
      return apiRequest<MarketplaceStorefrontCard[]>(
        `/marketplace/artisans/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
  });

  const { data: goods, isLoading: loadingGoods } = useQuery({
    queryKey: ["marketplace-goods", search, category, location, exactOnly],
    queryFn: () => {
      const params = buildLocationQuery();
      params.set("product_type", "goods");
      return apiRequest<MarketplaceProductCard[]>(
        `/marketplace/products/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
  });

  const { data: services, isLoading: loadingServices } = useQuery({
    queryKey: ["marketplace-services", search, category, location, exactOnly],
    queryFn: () => {
      const params = buildLocationQuery();
      params.set("product_type", "service");
      return apiRequest<MarketplaceProductCard[]>(
        `/marketplace/products/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
  });

  const calloutMutation = useMutation({
    mutationFn: () => {
      if (!calloutTarget) throw new Error("No artisan selected.");
      return apiRequest(`/storefronts/${calloutTarget.slug}/inquiries/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          inquiry_type: "work_callout",
          urgency,
          buyer_name: buyerName,
          buyer_phone: buyerPhone,
          customer_ward: location.wardId || null,
          customer_polling_unit: location.pollingUnitId || null,
          customer_address: customerAddress,
          budget_amount: budgetAmount.trim() ? budgetAmount.trim() : null,
          message: calloutMessage,
        }),
      });
    },
    onSuccess: () => {
      setCalloutError("");
      setCalloutSuccess(true);
      setBuyerName("");
      setBuyerPhone("");
      setCustomerAddress("");
      setBudgetAmount("");
      setCalloutMessage("");
    },
    onError: (err) => {
      setCalloutError(err instanceof Error ? err.message : "Could not send call-out request.");
    },
  });

  const hasLocationFilter = !!(
    location.stateId ||
    location.lgaId ||
    location.wardId ||
    location.pollingUnitId
  );

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[64px] max-w-[1180px] items-center justify-between gap-2 px-4 sm:min-h-[70px] sm:px-5">
          <Link href="/" className="flex min-w-0 items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand sm:h-9 sm:w-9">
              <Wrench className="h-4 w-4" />
            </div>
            <span className="truncate text-sm font-extrabold tracking-tight text-plum sm:text-base">
              ArtisanOS <span className="hidden sm:inline">Nigeria</span>
            </span>
          </Link>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
            {user ? (
              <>
                <Link href="/escrow">
                  <Button variant="outline" size="sm" className="whitespace-nowrap px-2.5 sm:px-4">
                    <Lock className="h-3.5 w-3.5 text-emerald-700" />
                    <span className="hidden sm:inline">Escrows</span>
                  </Button>
                </Link>
                {user.memberships.length > 0 ? (
                  <Link href="/dashboard">
                    <Button size="sm" className="whitespace-nowrap px-3 sm:px-4">
                      <span className="hidden sm:inline">Open workspace</span>
                      <span className="sm:hidden">Workspace</span>
                    </Button>
                  </Link>
                ) : (
                  <span className="hidden rounded-full border border-line bg-white px-3.5 py-1.5 text-xs font-semibold text-plum sm:inline-block">
                    {user.full_name}
                    {user.ward_name ? ` · ${user.ward_name}` : ""}
                  </span>
                )}
              </>
            ) : (
              <>
                <Link href="/login">
                  <Button variant="ghost" size="sm" className="px-2.5 sm:px-4">
                    Sign in
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="sm" className="px-3 sm:px-4">
                    <span className="hidden sm:inline">Join / List craft</span>
                    <span className="sm:hidden">Join</span>
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hyper-Local Nigeria Search Hero */}
      <section className="mezer-hero-bg relative overflow-hidden border-b border-line-soft py-8 sm:py-12">
        <div
          aria-hidden="true"
          className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[440px] w-[440px] rounded-full"
        />
        <div className="relative mx-auto max-w-[1180px] space-y-5 px-4 sm:px-5">
          <div>
            <div className="mezer-eyebrow">
              <Navigation className="h-3.5 w-3.5 shrink-0" />
              Nationwide Coverage · All 36 States, FCT &amp; 774 LGAs
            </div>
            <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-plum sm:text-4xl">
              Find Verified Artisans in Your Area
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm text-ink-soft sm:text-base">
              Pick your neighborhood to browse local tradespeople and workshops nearby.
              Book on-site services or purchase handcrafted goods directly.
            </p>
          </div>

          {/* Unified Search & Location Filter Card */}
          <Card className="rounded-mezer-lg border-line bg-white/95 shadow-card">
            <CardContent className="space-y-4 p-5">
              <div className="grid gap-3 sm:grid-cols-[1.4fr_0.8fr]">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-ink-faint" />
                  <Input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search skill, craft, product, or artisan (e.g. solar inverter, burst pipe, agbada, loafers)..."
                    className="mt-0 bg-white pl-10"
                  />
                </div>
                <Select
                  aria-label="Filter artisan trade"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="mt-0 bg-white"
                >
                  <option value="">All Artisan Trades &amp; Crafts</option>
                  {ARTISAN_CATEGORIES.map((c) => {
                    const count = categoryCounts?.find((row) => row.code === c.value)?.artisan_count;
                    return (
                      <option key={c.value} value={c.value}>
                        {c.label}
                        {typeof count === "number" && count > 0 ? ` (${count})` : ""}
                      </option>
                    );
                  })}
                </Select>
              </div>

              <div className="rounded-mezer-sm border border-line-soft bg-surface p-4">
                <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 text-xs font-extrabold uppercase tracking-wider text-plum">
                    <MapPin className="h-3.5 w-3.5 text-brand-700" />
                    Filter by Your Location
                  </span>
                  <div className="flex flex-wrap items-center gap-4 text-xs font-semibold text-ink-soft">
                    {hasLocationFilter && (
                      <label className="inline-flex cursor-pointer items-center gap-1.5">
                        <input
                          type="checkbox"
                          className="accent-brand-700"
                          checked={exactOnly}
                          onChange={(e) => setExactOnly(e.target.checked)}
                        />
                        Exact area only
                      </label>
                    )}
                    <label className="inline-flex cursor-pointer items-center gap-1.5">
                      <input
                        type="checkbox"
                        className="accent-brand-700"
                        checked={availableOnly}
                        onChange={(e) => setAvailableOnly(e.target.checked)}
                      />
                      Available now
                    </label>
                    <label className="inline-flex cursor-pointer items-center gap-1.5">
                      <input
                        type="checkbox"
                        className="accent-brand-700"
                        checked={calloutOnly}
                        onChange={(e) => setCalloutOnly(e.target.checked)}
                      />
                      Home / On-site call-out
                    </label>
                  </div>
                </div>
                <NigeriaLocationPicker
                  value={location}
                  onChange={setLocation}
                  compact
                  allowCreateNew
                  idPrefix="mkt-loc"
                />
              </div>
            </CardContent>
          </Card>

          {/* Discovery Tabs */}
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            <div className="no-scrollbar flex w-full overflow-x-auto rounded-full border border-line bg-white p-1 shadow-mezer-sm sm:inline-flex sm:w-auto">
              <button
                type="button"
                onClick={() => setTab("artisans")}
                className={`inline-flex shrink-0 flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 text-xs font-semibold transition-colors sm:flex-initial sm:px-4 sm:py-1.5 ${
                  tab === "artisans" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
                }`}
              >
                <Store className="h-3.5 w-3.5" /> Artisans ({artisans?.length ?? 0})
              </button>
              <button
                type="button"
                onClick={() => setTab("goods")}
                className={`inline-flex shrink-0 flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 text-xs font-semibold transition-colors sm:flex-initial sm:px-4 sm:py-1.5 ${
                  tab === "goods" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
                }`}
              >
                <ShoppingBag className="h-3.5 w-3.5" /> Goods ({goods?.length ?? 0})
              </button>
              <button
                type="button"
                onClick={() => setTab("services")}
                className={`inline-flex shrink-0 flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-2 text-xs font-semibold transition-colors sm:flex-initial sm:px-4 sm:py-1.5 ${
                  tab === "services" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
                }`}
              >
                <Briefcase className="h-3.5 w-3.5" /> Services ({services?.length ?? 0})
              </button>
            </div>

            {hasLocationFilter && (
              <span className="text-xs font-semibold text-brand-700">
                Sorted closest to your area first
              </span>
            )}
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-[1180px] space-y-6 px-4 py-8 sm:px-5 sm:py-10">
        {/* Quick Call-for-Work Modal */}
        {calloutTarget && (
          <div className="fixed inset-0 z-50 flex items-end justify-center bg-plum/55 p-0 backdrop-blur-sm sm:items-center sm:p-4">
            <Card className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-b-none rounded-t-mezer-lg sm:rounded-mezer-lg">
              <CardHeader className="flex flex-row items-start justify-between gap-3">
                <div>
                  <div className="mezer-eyebrow">Call Artisan for Work</div>
                  <h2 className="mt-1 text-lg font-extrabold text-plum">
                    {calloutTarget.organization_name}
                  </h2>
                  <p className="text-xs text-ink-soft">
                    {calloutTarget.category_label}
                    {calloutTarget.ward_name ? ` · ${calloutTarget.ward_name}` : ""}
                    {calloutTarget.callout_fee
                      ? ` · Call-out from ${formatCurrency(calloutTarget.callout_fee, calloutTarget.currency)}`
                      : ""}
                  </p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setCalloutTarget(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardContent>
                {calloutSuccess ? (
                  <div className="space-y-3 py-6 text-center">
                    <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
                    <h3 className="text-lg font-bold text-plum">Work Call-Out Sent!</h3>
                    <p className="text-sm text-ink-soft">
                      {calloutTarget.organization_name} has received your job request and contact
                      details. You can also call them directly right now:
                    </p>
                    <div className="flex flex-wrap justify-center gap-2 pt-2">
                      {buildTelHref(calloutTarget.phone) && (
                        <a href={buildTelHref(calloutTarget.phone)!}>
                          <Button size="sm">
                            <Phone className="h-3.5 w-3.5" /> Call {calloutTarget.phone}
                          </Button>
                        </a>
                      )}
                      <Button size="sm" variant="outline" onClick={() => setCalloutTarget(null)}>
                        Done
                      </Button>
                    </div>
                  </div>
                ) : (
                  <form
                    className="space-y-3.5"
                    onSubmit={(e) => {
                      e.preventDefault();
                      calloutMutation.mutate();
                    }}
                  >
                    {calloutError && (
                      <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                        {calloutError}
                      </div>
                    )}
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <Label htmlFor="co-name">Your name</Label>
                        <Input
                          id="co-name"
                          required
                          placeholder="e.g. Chika Obi"
                          value={buyerName}
                          onChange={(e) => setBuyerName(e.target.value)}
                        />
                      </div>
                      <div>
                        <Label htmlFor="co-phone">Phone / WhatsApp</Label>
                        <Input
                          id="co-phone"
                          required
                          placeholder="+2348012345678"
                          value={buyerPhone}
                          onChange={(e) => setBuyerPhone(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <Label htmlFor="co-urgency">How soon do you need work?</Label>
                        <Select
                          id="co-urgency"
                          value={urgency}
                          onChange={(e) => setUrgency(e.target.value as InquiryUrgency)}
                        >
                          <option value="emergency">Urgent / Immediate Call-Out</option>
                          <option value="today">Needed Today</option>
                          <option value="normal">Flexible / Scheduled</option>
                        </Select>
                      </div>
                      <div>
                        <Label htmlFor="co-budget">Estimated budget ({calloutTarget.currency}, optional)</Label>
                        <Input
                          id="co-budget"
                          type="number"
                          min="0"
                          placeholder="e.g. 15000"
                          value={budgetAmount}
                          onChange={(e) => setBudgetAmount(e.target.value)}
                        />
                      </div>
                    </div>

                    <div>
                      <Label htmlFor="co-addr">Street address / landmark for the job</Label>
                      <Input
                        id="co-addr"
                        placeholder="e.g. 14 Allen Avenue, opposite First Bank"
                        value={customerAddress}
                        onChange={(e) => setCustomerAddress(e.target.value)}
                      />
                    </div>

                    <div>
                      <Label htmlFor="co-msg">Describe the work needed</Label>
                      <Textarea
                        id="co-msg"
                        rows={3}
                        required
                        placeholder="Explain the fault, repair, measurement, or custom job..."
                        value={calloutMessage}
                        onChange={(e) => setCalloutMessage(e.target.value)}
                      />
                    </div>

                    <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:justify-end">
                      <Button
                        variant="outline"
                        className="w-full sm:w-auto"
                        onClick={() => setCalloutTarget(null)}
                      >
                        Cancel
                      </Button>
                      <Button
                        type="submit"
                        className="w-full sm:w-auto"
                        disabled={calloutMutation.isPending}
                      >
                        {calloutMutation.isPending ? "Sending..." : "Send work call-out"}
                      </Button>
                    </div>
                  </form>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* TAB 1: ARTISANS NEARBY */}
        {tab === "artisans" && (
          <>
            {loadingArtisans && (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                <Card className="h-64 animate-pulse bg-surface" />
                <Card className="h-64 animate-pulse bg-surface" />
                <Card className="h-64 animate-pulse bg-surface" />
              </div>
            )}
            {!loadingArtisans && !artisans?.length ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <MapPin className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">
                    No artisans found in this area yet
                  </h2>
                  <p className="mx-auto mt-1 max-w-md text-sm text-ink-soft">
                    Try unchecking &ldquo;Exact area only&rdquo; to expand to nearby neighborhoods in
                    the same LGA, or register your own artisan business here.
                  </p>
                  <div className="mt-4 flex justify-center gap-2">
                    {exactOnly && (
                      <Button size="sm" variant="outline" onClick={() => setExactOnly(false)}>
                        Include nearby areas
                      </Button>
                    )}
                    <Link href="/register">
                      <Button size="sm">Register as an artisan</Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {artisans?.map((art) => {
                  const avail = getAvailabilityBadge(art.availability_status);
                  const telHref = buildTelHref(art.phone);
                  const waHref = buildWhatsAppHref(
                    art.whatsapp_number || art.phone,
                    `Hello ${art.organization_name}, I found you on ArtisanOS and would like to inquire about ${art.category_label} work.`
                  );
                  return (
                    <Card
                      key={art.slug}
                      className="flex flex-col justify-between transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
                    >
                      <CardContent className="space-y-3 p-5">
                        {/* Top Badges: Category + Proximity */}
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <span className="rounded-full bg-surface-blush px-2.5 py-0.5 text-[11px] font-bold text-brand-700">
                            {art.category_label}
                          </span>
                          {art.proximity_label && (
                            <span
                              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-extrabold ${getProximityBadgeClasses(
                                art.proximity_tier
                              )}`}
                            >
                              <Navigation className="h-2.5 w-2.5" />
                              {art.proximity_label}
                              {art.distance_km !== null && art.distance_km > 0
                                ? ` · ${art.distance_km} km`
                                : ""}
                            </span>
                          )}
                        </div>

                        {/* Artisan Name & Verified */}
                        <div>
                          <div className="flex items-center gap-1.5">
                            <h2 className="text-lg font-extrabold text-plum">
                              {art.organization_name}
                            </h2>
                            {art.is_verified && (
                              <span title="Verified Artisan">
                                <BadgeCheck className="h-4 w-4 shrink-0 text-emerald-600" />
                              </span>
                            )}
                          </div>
                          {art.headline && (
                            <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-ink-soft">
                              {art.headline}
                            </p>
                          )}
                        </div>

                        {/* Availability, KYC Trust & Call-out fee */}
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-semibold ${avail.classes}`}
                          >
                            <span className={`h-1.5 w-1.5 rounded-full ${avail.dot}`} />
                            {avail.label}
                          </span>
                          {art.is_verified && (
                            <span
                              title={
                                art.cac_verified
                                  ? "Identity and registered business verified"
                                  : "Identity verified"
                              }
                              className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 font-semibold text-emerald-800"
                            >
                              <BadgeCheck className="h-3 w-3" />
                              {art.cac_verified ? "Verified Business" : "Verified"}
                            </span>
                          )}
                          {art.available_for_callout && (
                            <span className="rounded-full border border-line bg-surface px-2.5 py-0.5 font-semibold text-plum">
                              {art.callout_fee
                                ? `Call-out ${formatCurrency(art.callout_fee, art.currency)}`
                                : "On-site call-out"}
                            </span>
                          )}
                        </div>

                        {/* Hyper-local Ward / Polling Unit Location */}
                        <div className="rounded-xl border border-line-soft bg-surface p-2.5 text-xs">
                          <div className="flex items-start gap-1.5 text-plum">
                            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" />
                            <div className="min-w-0">
                              {art.polling_unit_name ? (
                                <>
                                  <div className="font-bold leading-snug">
                                    {art.polling_unit_name}
                                  </div>
                                  <div className="text-[11px] text-ink-soft">
                                    {[art.ward_name, art.lga_name, art.state_name]
                                      .filter(Boolean)
                                      .join(" · ")}
                                  </div>
                                </>
                              ) : art.ward_name ? (
                                <div className="font-semibold">
                                  {[art.ward_name, art.lga_name, art.state_name]
                                    .filter(Boolean)
                                    .join(" · ")}
                                </div>
                              ) : (
                                <div className="font-semibold">
                                  {[art.city, art.state_name, art.country].filter(Boolean).join(", ") ||
                                    "Nigeria"}
                                </div>
                              )}
                              {art.landmark && (
                                <div className="mt-0.5 truncate text-[11px] text-ink-faint">
                                  Landmark: {art.landmark}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Skills Tags */}
                        {art.skills && art.skills.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {art.skills.slice(0, 4).map((skill) => (
                              <span
                                key={skill}
                                className="rounded-full border border-line-soft bg-white px-2.5 py-0.5 text-[10px] font-semibold text-ink-soft"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        )}
                      </CardContent>

                      {/* Action Bar: Call Now, WhatsApp, Book Work, Visit Store */}
                      <div className="space-y-2 border-t border-line-soft px-5 py-3.5">
                        <div className="grid grid-cols-2 gap-2">
                          {telHref ? (
                            <a href={telHref} className="w-full">
                              <Button size="sm" className="w-full">
                                <Phone className="h-3.5 w-3.5" /> Call now
                              </Button>
                            </a>
                          ) : (
                            <Button
                              size="sm"
                              className="w-full"
                              onClick={() => {
                                setCalloutTarget(art);
                                setCalloutSuccess(false);
                                setCalloutError("");
                              }}
                            >
                              <Phone className="h-3.5 w-3.5" /> Call for work
                            </Button>
                          )}

                          {waHref ? (
                            <a
                              href={waHref}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="w-full"
                            >
                              <Button size="sm" variant="outline" className="w-full">
                                <MessageCircle className="h-3.5 w-3.5 text-emerald-700" /> WhatsApp
                              </Button>
                            </a>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full"
                              onClick={() => {
                                setCalloutTarget(art);
                                setCalloutSuccess(false);
                                setCalloutError("");
                              }}
                            >
                              Book work
                            </Button>
                          )}
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setCalloutTarget(art);
                              setCalloutSuccess(false);
                              setCalloutError("");
                            }}
                            className="text-xs font-bold text-brand-700 hover:underline"
                          >
                            Request job call-out
                          </button>
                          <Link
                            href={`/store/${art.slug}`}
                            className="inline-flex items-center gap-1 text-xs font-bold text-plum hover:text-brand-700"
                          >
                            Store ({art.published_product_count}) <ArrowRight className="h-3 w-3" />
                          </Link>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* TAB 2: GOODS & PRODUCTS */}
        {tab === "goods" && (
          <>
            {loadingGoods && <Card className="h-48 animate-pulse bg-surface" />}
            {!loadingGoods && !goods?.length ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <ShoppingBag className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">
                    No artisan goods match this location filter yet
                  </h2>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {goods?.map((p) => (
                  <Card
                    key={p.id}
                    className="flex flex-col justify-between transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
                  >
                    <CardContent className="space-y-2.5 p-5">
                      <div className="flex flex-wrap items-center justify-between gap-1.5">
                        <span className="rounded-full bg-surface-blush px-2.5 py-0.5 text-[11px] font-bold text-brand-700">
                          {formatStatusLabel(p.product_type)}
                        </span>
                        {p.proximity_label ? (
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${getProximityBadgeClasses(
                              p.proximity_tier
                            )}`}
                          >
                            {p.proximity_label}
                          </span>
                        ) : (
                          <span className="text-xs text-ink-faint">
                            {p.ward_name || p.organization_city}
                          </span>
                        )}
                      </div>
                      <h2 className="text-lg font-bold text-plum">{p.name}</h2>
                      <div className="text-xs font-semibold text-ink-soft">
                        by {p.organization_name} · {p.organization_category_label}
                      </div>
                      {p.description && (
                        <p className="line-clamp-2 text-xs text-ink-soft">{p.description}</p>
                      )}
                      {(p.polling_unit_name || p.ward_name) && (
                        <div className="flex items-center gap-1 text-[11px] text-ink-faint">
                          <MapPin className="h-3 w-3 text-brand-600" />
                          {[p.ward_name, p.lga_name, p.state_name].filter(Boolean).join(", ")}
                        </div>
                      )}
                      <div className="pt-1 text-xl font-extrabold text-plum">
                        {formatCurrency(p.price, p.currency)}
                      </div>
                    </CardContent>
                    <div className="border-t border-line-soft px-5 py-3.5">
                      <Link href={`/store/${p.storefront_slug}`}>
                        <Button size="sm" className="w-full">
                          Patronize / Order piece <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}

        {/* TAB 3: SERVICES */}
        {tab === "services" && (
          <>
            {loadingServices && <Card className="h-48 animate-pulse bg-surface" />}
            {!loadingServices && !services?.length ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <Briefcase className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">
                    No artisan services match this location filter yet
                  </h2>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {services?.map((srv) => (
                  <Card
                    key={srv.id}
                    className="flex flex-col justify-between transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
                  >
                    <CardContent className="space-y-2.5 p-5">
                      <div className="flex flex-wrap items-center justify-between gap-1.5">
                        <span className="rounded-full bg-surface-blush px-2.5 py-0.5 text-[11px] font-bold text-brand-700">
                          {srv.organization_category_label}
                        </span>
                        {srv.proximity_label && (
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${getProximityBadgeClasses(
                              srv.proximity_tier
                            )}`}
                          >
                            {srv.proximity_label}
                          </span>
                        )}
                      </div>
                      <h2 className="text-lg font-bold text-plum">{srv.name}</h2>
                      <div className="text-xs font-semibold text-ink-soft">
                        by {srv.organization_name}
                      </div>
                      {srv.description && (
                        <p className="line-clamp-2 text-xs text-ink-soft">{srv.description}</p>
                      )}
                      {(srv.ward_name || srv.lga_name) && (
                        <div className="flex items-center gap-1 text-[11px] text-ink-faint">
                          <MapPin className="h-3 w-3 text-brand-600" />
                          {[srv.ward_name, srv.lga_name, srv.state_name].filter(Boolean).join(", ")}
                        </div>
                      )}
                      <div className="pt-1 text-xl font-extrabold text-plum">
                        From {formatCurrency(srv.price, srv.currency)}
                      </div>
                    </CardContent>
                    <div className="flex flex-col gap-2 border-t border-line-soft px-4 py-3.5 sm:flex-row sm:px-5">
                      {buildTelHref(srv.organization_phone) && (
                        <a href={buildTelHref(srv.organization_phone)!} className="w-full sm:w-auto">
                          <Button size="sm" variant="outline" className="w-full sm:w-auto">
                            <Phone className="h-3.5 w-3.5" /> Call
                          </Button>
                        </a>
                      )}
                      <Link href={`/store/${srv.storefront_slug}`} className="w-full sm:flex-1">
                        <Button size="sm" className="w-full">
                          Book service <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default function MarketplacePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-soft">
          Loading Nigerian Artisan Marketplace...
        </div>
      }
    >
      <MarketplaceContent />
    </Suspense>
  );
}
