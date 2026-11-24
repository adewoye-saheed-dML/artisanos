"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BadgeCheck,
  Briefcase,
  CheckCircle2,
  Lock,
  MapPin,
  MessageCircle,
  Phone,
  ShoppingBag,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import {
  NigeriaLocationPicker,
  type NigeriaLocationValue,
} from "@/components/locations/nigeria-location-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import {
  buildTelHref,
  buildWhatsAppHref,
  getAvailabilityBadge,
} from "@/lib/artisans";
import { formatCurrency, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  EscrowTransaction,
  InquiryType,
  InquiryUrgency,
  Product,
  PublicStorefrontResponse,
} from "@/types/api";

export default function PublicStorefrontPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const slug = params.slug;

  const [typeFilter, setTypeFilter] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showInquiry, setShowInquiry] = useState(false);

  // Escrow protection modal state
  const [showEscrowModal, setShowEscrowModal] = useState(false);
  const [escrowJobTitle, setEscrowJobTitle] = useState("");
  const [escrowAmount, setEscrowAmount] = useState("");
  const [escrowDesc, setEscrowDesc] = useState("");
  const [escrowAdvancePct, setEscrowAdvancePct] = useState("0");
  const [escrowError, setEscrowError] = useState("");

  const [inquiryType, setInquiryType] = useState<InquiryType>("work_callout");
  const [urgency, setUrgency] = useState<InquiryUrgency>("today");
  const [buyerName, setBuyerName] = useState("");
  const [buyerPhone, setBuyerPhone] = useState("");
  const [buyerEmail, setBuyerEmail] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [preferredDate, setPreferredDate] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [budgetAmount, setBudgetAmount] = useState("");
  const [customerLocation, setCustomerLocation] = useState<NigeriaLocationValue>({
    stateId: "",
    lgaId: "",
    wardId: "",
    pollingUnitId: "",
  });
  const [message, setMessage] = useState("");
  const [inquiryError, setInquiryError] = useState("");
  const [inquirySent, setInquirySent] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-storefront", slug],
    queryFn: () =>
      apiRequest<PublicStorefrontResponse>(`/storefronts/${slug}/`, {
        skipOrgHeader: true,
      }),
    enabled: !!slug,
    retry: false,
  });

  const inquiryMutation = useMutation({
    mutationFn: () =>
      apiRequest(`/storefronts/${slug}/inquiries/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          product: selectedProduct?.id || null,
          inquiry_type: inquiryType,
          urgency,
          buyer_name: buyerName,
          buyer_phone: buyerPhone,
          buyer_email: buyerEmail,
          customer_ward: customerLocation.wardId || null,
          customer_polling_unit: customerLocation.pollingUnitId || null,
          customer_address: customerAddress,
          preferred_date: preferredDate || null,
          quantity: Math.max(1, Number(quantity) || 1),
          budget_amount: budgetAmount.trim() ? budgetAmount.trim() : null,
          message,
        }),
      }),
    onSuccess: () => {
      setInquiryError("");
      setInquirySent(true);
      setBuyerName("");
      setBuyerPhone("");
      setBuyerEmail("");
      setCustomerAddress("");
      setPreferredDate("");
      setQuantity("1");
      setBudgetAmount("");
      setMessage("");
    },
    onError: (err) => {
      setInquiryError(err instanceof Error ? err.message : "Could not send request.");
    },
  });

  const createEscrowMutation = useMutation({
    mutationFn: () =>
      apiRequest<EscrowTransaction>("/escrow/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          organization_slug: slug,
          job_title: escrowJobTitle,
          job_description: escrowDesc,
          total_amount: escrowAmount,
          materials_advance_pct: Number(escrowAdvancePct) || 0,
        }),
      }),
    onSuccess: () => {
      setEscrowError("");
      setShowEscrowModal(false);
      router.push("/escrow");
    },
    onError: (err) => {
      setEscrowError(err instanceof Error ? err.message : "Could not open escrow contract.");
    },
  });

  const sf = data?.storefront;
  const filteredProducts = (data?.products || []).filter((p) =>
    typeFilter ? p.product_type === typeFilter : true
  );
  const telHref = buildTelHref(sf?.phone || sf?.whatsapp_number);
  const waHref = buildWhatsAppHref(
    sf?.whatsapp_number || sf?.phone,
    sf
      ? `Hello ${sf.organization_name}, I found your storefront on ArtisanOS and would like to patronize your ${sf.category_label} services.`
      : undefined
  );
  const avail = sf ? getAvailabilityBadge(sf.availability_status) : null;

  function openCalloutModal(product: Product | null = null) {
    setSelectedProduct(product);
    if (product) {
      setInquiryType(product.product_type === "service" ? "service_booking" : "product_order");
      setUrgency("normal");
    } else {
      setInquiryType("work_callout");
      setUrgency("today");
    }
    setInquirySent(false);
    setInquiryError("");
    setShowInquiry(true);
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[64px] max-w-[1180px] items-center justify-between gap-2 px-4 sm:min-h-[68px] sm:gap-3 sm:px-5">
          <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
            <Link
              href="/marketplace"
              className="inline-flex shrink-0 items-center gap-1 rounded-full border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-ink-soft hover:border-brand-300 hover:text-brand-700 sm:border-0 sm:bg-transparent sm:p-0"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Marketplace</span>
            </Link>
            <span className="hidden text-line sm:inline">|</span>
            <Link href="/" className="flex min-w-0 items-center gap-2">
              <div className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand sm:flex">
                <Wrench className="h-4 w-4" />
              </div>
              <span className="truncate text-sm font-extrabold tracking-tight text-plum">
                {sf?.organization_name || "ArtisanOS Storefront"}
              </span>
            </Link>
          </div>
          {sf && (
            <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
              {telHref && (
                <a href={telHref} className="hidden sm:inline-block">
                  <Button size="sm" variant="outline">
                    <Phone className="h-3.5 w-3.5" /> Call now
                  </Button>
                </a>
              )}
              <Button size="sm" className="px-3 sm:px-4" onClick={() => openCalloutModal(null)}>
                <Briefcase className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Call for work</span>
                <span className="sm:hidden">Book</span>
              </Button>
            </div>
          )}
        </div>
      </header>

      {isLoading && (
        <div className="mx-auto max-w-[1180px] px-5 py-16">
          <Card className="h-56 animate-pulse bg-surface" />
        </div>
      )}

      {error && (
        <div className="mx-auto max-w-lg px-5 py-20 text-center">
          <Card className="rounded-mezer-lg">
            <CardContent className="py-12">
              <div className="mezer-eyebrow justify-center">Storefront Unavailable</div>
              <h1 className="mt-2 text-xl font-extrabold text-plum">Storefront not found</h1>
              <p className="mt-1.5 text-sm text-ink-soft">
                {error instanceof Error
                  ? error.message
                  : "This storefront is private or does not exist."}
              </p>
              <Link href="/marketplace" className="mt-5 inline-block">
                <Button size="sm" variant="outline">
                  Find nearby artisans
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      )}

      {sf && data && (
        <>
          {/* Velvet Plum Artisan Hero */}
          <section className="relative overflow-hidden bg-plum py-10 text-white sm:py-14">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-brand-500/25 blur-3xl"
            />
            <div className="relative mx-auto max-w-[1180px] space-y-5 px-4 sm:px-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mezer-eyebrow-light">
                  <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                  {sf.category_label}
                </span>
                {sf.is_verified && (
                  <span
                    title={
                      sf.cac_verified
                        ? "Identity and business registration verified"
                        : "Identity verified"
                    }
                    className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-3 py-0.5 text-[11px] font-bold text-emerald-200"
                  >
                    <BadgeCheck className="h-3.5 w-3.5" />
                    {sf.cac_verified ? "Verified Business" : "Verified Artisan"}
                  </span>
                )}
                {avail && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-0.5 text-[11px] font-bold text-white">
                    <span className={`h-2 w-2 rounded-full ${avail.dot}`} />
                    {avail.label}
                  </span>
                )}
              </div>

              <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
                <div>
                  <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-5xl">
                    {sf.organization_name}
                  </h1>
                  {sf.headline && (
                    <p className="mt-3 max-w-2xl text-lg text-[#ffdce6]">{sf.headline}</p>
                  )}
                  {sf.bio && (
                    <p className="mt-2 max-w-2xl text-sm leading-relaxed text-plum-soft">
                      {sf.bio}
                    </p>
                  )}

                  {/* Hyper-local Nigerian Address & Coverage */}
                  <div className="mt-5 flex flex-wrap items-center gap-2.5 text-xs text-plum-soft">
                    {sf.polling_unit_name && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/12 px-3 py-1.5 font-semibold text-white">
                        <MapPin className="h-3.5 w-3.5 text-brand-300" />
                        {sf.polling_unit_name}
                      </span>
                    )}
                    {(sf.ward_name || sf.lga_name || sf.state_name) && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5">
                        {[sf.ward_name, sf.lga_name, sf.state_name]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    )}
                    {sf.landmark && (
                      <span className="rounded-full bg-white/10 px-3 py-1.5">
                        Landmark: {sf.landmark}
                      </span>
                    )}
                    {sf.years_experience ? (
                      <span className="rounded-full bg-white/10 px-3 py-1.5">
                        {sf.years_experience}+ yrs experience
                      </span>
                    ) : null}
                    {sf.callout_fee && (
                      <span className="rounded-full bg-brand-600/40 px-3 py-1.5 font-semibold text-[#ffdce6]">
                        Call-out from {formatCurrency(sf.callout_fee, sf.currency)}
                      </span>
                    )}
                  </div>

                  {sf.service_ward_names && sf.service_ward_names.length > 0 && (
                    <div className="mt-3 text-xs text-plum-soft">
                      Also covers wards:{" "}
                      <span className="font-semibold text-white">
                        {sf.service_ward_names.join(", ")}
                      </span>
                    </div>
                  )}

                  {sf.skills && sf.skills.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {sf.skills.map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full border border-white/15 bg-white/[0.06] px-3 py-1 text-[11px] font-semibold text-white"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Direct Contact / Call-Out Box */}
                <div className="rounded-mezer-md border border-white/15 bg-white/[0.08] p-5 backdrop-blur-sm">
                  <div className="text-xs font-extrabold uppercase tracking-wider text-[#ffdce6]">
                    Hire or Patronize Directly
                  </div>
                  <div className="mt-3 space-y-2.5">
                    {telHref && (
                      <a href={telHref} className="block">
                        <Button className="w-full" size="md">
                          <Phone className="h-4 w-4" /> Call {sf.phone || sf.whatsapp_number}
                        </Button>
                      </a>
                    )}
                    {waHref && (
                      <a
                        href={waHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block"
                      >
                        <Button variant="light" className="w-full" size="md">
                          <MessageCircle className="h-4 w-4 text-emerald-700" /> Chat on WhatsApp
                        </Button>
                      </a>
                    )}
                    <Button
                      variant="outline"
                      size="md"
                      className="w-full border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                      onClick={() => openCalloutModal(null)}
                    >
                      <Briefcase className="h-4 w-4" /> Send Job / Call-Out Request
                    </Button>
                    {sf.is_verified && (
                      <Button
                        size="md"
                        className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
                        onClick={() => {
                          setEscrowJobTitle(`${sf.category_label} Work`);
                          setEscrowAmount("");
                          setEscrowDesc("");
                          setEscrowError("");
                          setShowEscrowModal(true);
                        }}
                      >
                        <Lock className="h-4 w-4" /> Hire with Escrow Protection
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <main className="mx-auto max-w-[1180px] space-y-8 px-5 py-12">
            {/* Escrow Protection Modal */}
            {showEscrowModal && (
              <Card className="rounded-mezer-lg border-emerald-300 bg-emerald-50/40">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <div className="inline-flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-wider text-emerald-800">
                      <Lock className="h-3.5 w-3.5" /> Pay Fully Only After Work Is Completed
                    </div>
                    <h2 className="mt-1 text-lg font-bold text-plum">
                      Open Escrow Contract with {sf.organization_name}
                    </h2>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setShowEscrowModal(false)}>
                    <X className="h-4 w-4" />
                  </Button>
                </CardHeader>
                <CardContent>
                  {!user ? (
                    <div className="space-y-3 py-4 text-center">
                      <p className="text-sm text-ink-soft">
                        Sign in or create a free Customer account to fund this job via ArtisanOS
                        Escrow Protection and receive your private 6-digit Completion PIN.
                      </p>
                      <div className="flex justify-center gap-2">
                        <Link href="/login">
                          <Button size="sm" variant="outline">
                            Sign in
                          </Button>
                        </Link>
                        <Link href="/register">
                          <Button size="sm">Create Customer Account</Button>
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <form
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        createEscrowMutation.mutate();
                      }}
                    >
                      {escrowError && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                          {escrowError}
                        </div>
                      )}
                      <div className="grid gap-4 sm:grid-cols-3">
                        <div className="sm:col-span-2">
                          <Label htmlFor="esc-title">Job or item title</Label>
                          <Input
                            id="esc-title"
                            required
                            className="bg-white"
                            value={escrowJobTitle}
                            onChange={(e) => setEscrowJobTitle(e.target.value)}
                          />
                        </div>
                        <div>
                          <Label htmlFor="esc-amt">Agreed amount ({sf.currency})</Label>
                          <Input
                            id="esc-amt"
                            type="number"
                            min="500"
                            step="0.01"
                            required
                            className="bg-white"
                            placeholder="e.g. 50000"
                            value={escrowAmount}
                            onChange={(e) => setEscrowAmount(e.target.value)}
                          />
                        </div>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <Label htmlFor="esc-adv">Protection split</Label>
                          <Select
                            id="esc-adv"
                            className="bg-white"
                            value={escrowAdvancePct}
                            onChange={(e) => setEscrowAdvancePct(e.target.value)}
                          >
                            <option value="0">100% locked in Escrow until work is done (Recommended)</option>
                            <option value="20">80% locked in Escrow / 20% materials mobilization</option>
                            <option value="30">70% locked in Escrow / 30% materials mobilization</option>
                          </Select>
                        </div>
                        <div>
                          <Label htmlFor="esc-desc">Scope &amp; completion criteria</Label>
                          <Input
                            id="esc-desc"
                            className="bg-white"
                            placeholder="Describe what must be finished before release..."
                            value={escrowDesc}
                            onChange={(e) => setEscrowDesc(e.target.value)}
                          />
                        </div>
                      </div>
                      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button
                          variant="outline"
                          className="w-full sm:w-auto"
                          onClick={() => setShowEscrowModal(false)}
                        >
                          Cancel
                        </Button>
                        <Button
                          type="submit"
                          className="w-full sm:w-auto"
                          disabled={createEscrowMutation.isPending}
                        >
                          <Lock className="h-3.5 w-3.5" />
                          {createEscrowMutation.isPending
                            ? "Opening escrow..."
                            : "Create Escrow & Proceed to Fund"}
                        </Button>
                      </div>
                    </form>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Call-for-Work / Patronage Inquiry Panel */}
            {showInquiry && (
              <Card className="rounded-mezer-lg border-brand-300">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <div className="mezer-eyebrow">
                      {selectedProduct ? "Patronize Listing" : "Call Artisan for Work"}
                    </div>
                    <h2 className="mt-1 text-lg font-bold text-plum">
                      {selectedProduct
                        ? `${selectedProduct.name} (${formatCurrency(
                            selectedProduct.price,
                            selectedProduct.currency
                          )})`
                        : `Request Work or Message ${sf.organization_name}`}
                    </h2>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setShowInquiry(false)}>
                    <X className="h-4 w-4" />
                  </Button>
                </CardHeader>
                <CardContent>
                  {inquirySent ? (
                    <div className="py-6 text-center">
                      <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
                      <h3 className="mt-2 text-lg font-bold text-plum">Request Sent!</h3>
                      <p className="mt-1 text-sm text-ink-soft">
                        {sf.organization_name} has been notified and will contact you shortly.
                      </p>
                    </div>
                  ) : (
                    <form
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        inquiryMutation.mutate();
                      }}
                    >
                      {inquiryError && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                          {inquiryError}
                        </div>
                      )}

                      <div className="grid gap-4 sm:grid-cols-3">
                        <div>
                          <Label htmlFor="inq-type">Request type</Label>
                          <Select
                            id="inq-type"
                            value={inquiryType}
                            onChange={(e) => setInquiryType(e.target.value as InquiryType)}
                          >
                            <option value="work_callout">Call for Work / On-Site Job</option>
                            <option value="product_order">Buy Product / Goods</option>
                            <option value="service_booking">Book Service</option>
                            <option value="general">General Inquiry</option>
                          </Select>
                        </div>
                        <div>
                          <Label htmlFor="inq-urgency">Urgency</Label>
                          <Select
                            id="inq-urgency"
                            value={urgency}
                            onChange={(e) => setUrgency(e.target.value as InquiryUrgency)}
                          >
                            <option value="emergency">Urgent / Immediate Call-Out</option>
                            <option value="today">Needed Today</option>
                            <option value="normal">Flexible / Scheduled</option>
                          </Select>
                        </div>
                        {selectedProduct ? (
                          <div>
                            <Label htmlFor="inq-qty">Quantity</Label>
                            <Input
                              id="inq-qty"
                              type="number"
                              min={1}
                              value={quantity}
                              onChange={(e) => setQuantity(e.target.value)}
                            />
                          </div>
                        ) : (
                          <div>
                            <Label htmlFor="inq-budget">Budget ({sf.currency}, optional)</Label>
                            <Input
                              id="inq-budget"
                              type="number"
                              min="0"
                              placeholder="e.g. 20000"
                              value={budgetAmount}
                              onChange={(e) => setBudgetAmount(e.target.value)}
                            />
                          </div>
                        )}
                      </div>

                      <div className="grid gap-4 sm:grid-cols-3">
                        <div>
                          <Label htmlFor="inq-name">Your name</Label>
                          <Input
                            id="inq-name"
                            required
                            value={buyerName}
                            onChange={(e) => setBuyerName(e.target.value)}
                          />
                        </div>
                        <div>
                          <Label htmlFor="inq-phone">Phone / WhatsApp</Label>
                          <Input
                            id="inq-phone"
                            required
                            placeholder="+2348012345678"
                            value={buyerPhone}
                            onChange={(e) => setBuyerPhone(e.target.value)}
                          />
                        </div>
                        <div>
                          <Label htmlFor="inq-email">Email (optional)</Label>
                          <Input
                            id="inq-email"
                            type="email"
                            value={buyerEmail}
                            onChange={(e) => setBuyerEmail(e.target.value)}
                          />
                        </div>
                      </div>

                      {/* Optional Customer Ward / Polling Unit for On-Site Work or Delivery */}
                      <div className="rounded-mezer-sm border border-line-soft bg-surface p-4 space-y-3">
                        <div className="text-xs font-extrabold uppercase tracking-wider text-plum">
                          Your Location (Optional — helps the artisan reach your area)
                        </div>
                        <NigeriaLocationPicker
                          value={customerLocation}
                          onChange={setCustomerLocation}
                          compact
                          idPrefix="cust-loc"
                        />
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <Label htmlFor="inq-addr">Street address / house / landmark</Label>
                            <Input
                              id="inq-addr"
                              className="bg-white"
                              placeholder="e.g. 12 Adeola Odeku, Flat 2B"
                              value={customerAddress}
                              onChange={(e) => setCustomerAddress(e.target.value)}
                            />
                          </div>
                          <div>
                            <Label htmlFor="inq-date">Preferred date (optional)</Label>
                            <Input
                              id="inq-date"
                              type="date"
                              className="bg-white"
                              value={preferredDate}
                              onChange={(e) => setPreferredDate(e.target.value)}
                            />
                          </div>
                        </div>
                      </div>

                      <div>
                        <Label htmlFor="inq-msg">Job details / order instructions</Label>
                        <Textarea
                          id="inq-msg"
                          rows={3}
                          required
                          placeholder="Describe the work needed, item specifications, size, or preferred time..."
                          value={message}
                          onChange={(e) => setMessage(e.target.value)}
                        />
                      </div>

                      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button
                          variant="outline"
                          className="w-full sm:w-auto"
                          onClick={() => setShowInquiry(false)}
                        >
                          Cancel
                        </Button>
                        <Button
                          type="submit"
                          className="w-full sm:w-auto"
                          disabled={inquiryMutation.isPending}
                        >
                          {inquiryMutation.isPending ? "Sending..." : "Submit request"}
                        </Button>
                      </div>
                    </form>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Goods & Services Catalogue Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-extrabold tracking-tight text-plum">
                Goods &amp; Services ({filteredProducts.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {[
                  ["", "All"],
                  ["ready_made", "Ready-Made Goods"],
                  ["made_to_order", "Made to Order"],
                  ["service", "Services"],
                ].map(([val, lbl]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setTypeFilter(val)}
                    className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition-colors ${
                      typeFilter === val
                        ? "border-plum bg-plum text-white"
                        : "border-line bg-white text-ink-soft hover:border-brand-300"
                    }`}
                  >
                    {lbl}
                  </button>
                ))}
              </div>
            </div>

            {filteredProducts.length === 0 ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <ShoppingBag className="mx-auto h-8 w-8 text-brand-700" />
                  <h3 className="mt-3 text-base font-bold text-plum">No listings published yet</h3>
                  <p className="mt-1 text-sm text-ink-soft">
                    Use &ldquo;Call for work&rdquo; above to contact this artisan directly for
                    custom jobs or quotes.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {filteredProducts.map((prod) => (
                  <Card
                    key={prod.id}
                    className="flex flex-col justify-between transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
                  >
                    <CardContent className="space-y-3 p-6">
                      <div className="flex items-center justify-between">
                        <span className="rounded-full bg-surface-blush px-3 py-0.5 text-[11px] font-bold text-brand-700">
                          {formatStatusLabel(prod.product_type)}
                        </span>
                        {prod.track_inventory && (
                          <span
                            className={`text-xs font-semibold ${
                              prod.stock_quantity > 0 ? "text-emerald-700" : "text-red-600"
                            }`}
                          >
                            {prod.stock_quantity > 0
                              ? `${prod.stock_quantity} in stock`
                              : "Sold out"}
                          </span>
                        )}
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-plum">{prod.name}</h3>
                        <p className="text-xs text-ink-faint">{prod.category}</p>
                      </div>
                      {prod.description && (
                        <p className="text-sm leading-relaxed text-ink-soft">{prod.description}</p>
                      )}
                      <div className="pt-2 text-xl font-extrabold text-plum">
                        {formatCurrency(prod.price, prod.currency)}
                      </div>
                    </CardContent>
                    <div className="flex flex-col gap-2 border-t border-line-soft px-4 py-3.5 sm:flex-row sm:px-6 sm:py-4">
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full sm:flex-1"
                        onClick={() => openCalloutModal(prod)}
                      >
                        {prod.product_type === "service" ? "Inquire" : "Order"}
                      </Button>
                      {sf.is_verified && (
                        <Button
                          size="sm"
                          className="w-full sm:flex-1"
                          onClick={() => {
                            setEscrowJobTitle(prod.name);
                            setEscrowAmount(prod.price);
                            setEscrowDesc(prod.description || "");
                            setEscrowError("");
                            setShowEscrowModal(true);
                          }}
                        >
                          <Lock className="h-3.5 w-3.5" /> Pay via Escrow
                        </Button>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </main>
        </>
      )}
    </div>
  );
}
