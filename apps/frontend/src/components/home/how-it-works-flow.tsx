"use client";

import {
  ArrowRight,
  BadgeCheck,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  MapPin,
  PhoneCall,
  ShieldCheck,
  ShoppingBag,
  Store,
  UserCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

interface FlowStep {
  number: string;
  shortTitle: string;
  label: string;
  headline: string;
  body: string;
  previewEyebrow: string;
  previewTitle: string;
  previewSubtitle: string;
  previewRows: { label: string; value: string; highlight?: boolean }[];
  icon: typeof MapPin;
}

const CUSTOMER_STEPS: FlowStep[] = [
  {
    number: "01",
    shortTitle: "Select location",
    label: "Hyper-Local Discovery",
    headline: "Discover skilled professionals right in your neighborhood",
    body: "Auto-detect your location or pick your State, LGA, and neighborhood. ArtisanOS ranks verified artisans closest to your address first, cutting wait times and call-out fees.",
    previewEyebrow: "Location Matched",
    previewTitle: "Anifowoshe · Ikeja, Lagos",
    previewSubtitle: "Ranked from your exact neighborhood outward",
    previewRows: [
      { label: "Nearest area", value: "Allen Roundabout Axis", highlight: true },
      { label: "Nearby availability", value: "14 verified artisans within 2 km" },
      { label: "Trades ready", value: "Electrical, Plumbing, Tailoring, Carpentry" },
    ],
    icon: MapPin,
  },
  {
    number: "02",
    shortTitle: "Compare & contact",
    label: "Direct Contact",
    headline: "Review verified profiles and reach out directly",
    body: "Compare live availability, transparent call-out rates, service listings, and ready-made goods. Call or message your chosen artisan on WhatsApp to agree on scope and timing.",
    previewEyebrow: "Verified Profile",
    previewTitle: "VoltCraft Electrical Services",
    previewSubtitle: "Ikeja · 0.8 km away · Available today",
    previewRows: [
      { label: "Status", value: "Verified Business", highlight: true },
      { label: "Call-out rate", value: "From ₦4,000" },
      { label: "Contact", value: "Direct phone call & WhatsApp enabled" },
    ],
    icon: PhoneCall,
  },
  {
    number: "03",
    shortTitle: "Secure booking",
    label: "Payment Protection",
    headline: "Fund your booking safely while work is underway",
    body: "Place your agreed amount in protected holding before work begins and receive a private 6-digit completion code. The artisan starts with confidence while your payment stays protected.",
    previewEyebrow: "Protected Booking",
    previewTitle: "Reference #ESC-2026-481A",
    previewSubtitle: "Funds held securely until customer sign-off",
    previewRows: [
      { label: "Amount held", value: "₦50,000.00", highlight: true },
      { label: "Completion code", value: "Private 6-digit PIN issued" },
      { label: "Protection", value: "Dispute review available if needed" },
    ],
    icon: ShieldCheck,
  },
  {
    number: "04",
    shortTitle: "Confirm & release",
    label: "Completion Sign-Off",
    headline: "Inspect the finished job and release payout",
    body: "Once the repair is finished or your custom item is delivered, enter your private completion code to settle payment directly to the artisan's bank account.",
    previewEyebrow: "Sign-Off Complete",
    previewTitle: "Customer confirmation recorded",
    previewSubtitle: "Full payout settled directly to artisan",
    previewRows: [
      { label: "Verification", value: "Completion code confirmed", highlight: true },
      { label: "Settlement", value: "Disbursed to artisan bank account" },
      { label: "Receipt", value: "Saved to your booking history" },
    ],
    icon: CheckCircle2,
  },
];

const ARTISAN_STEPS: FlowStep[] = [
  {
    number: "01",
    shortTitle: "Verify profile",
    label: "Artisan Onboarding",
    headline: "Create your account and build instant local credibility",
    body: "Register your trade and submit your identity and workshop details for review. A verified storefront reassures homeowners and businesses booking you for on-site visits or custom orders.",
    previewEyebrow: "Profile Status",
    previewTitle: "Verified Artisan Storefront",
    previewSubtitle: "Approved and discoverable across your area",
    previewRows: [
      { label: "Verification", value: "Approved & Active", highlight: true },
      { label: "Storefront link", value: "artisanos.ng/store/your-workshop" },
      { label: "Visibility", value: "Listed in public marketplace" },
    ],
    icon: ShieldCheck,
  },
  {
    number: "02",
    shortTitle: "Pin service areas",
    label: "Local Visibility",
    headline: "Appear first when nearby customers search your trade",
    body: "Pin your workshop location and add neighboring areas you cover. Customers searching nearby see your profile, availability, and direct contact details at the top.",
    previewEyebrow: "Coverage Map",
    previewTitle: "Surulere · Bode Thomas Base",
    previewSubtitle: "Primary area + 3 surrounding neighborhoods",
    previewRows: [
      { label: "Primary area", value: "Bode Thomas / Adeniran Ogunsanya", highlight: true },
      { label: "Extra areas", value: "Aguda, Ijesha, Lawanson" },
      { label: "On-site calls", value: "Enabled · Same-day response" },
    ],
    icon: MapPin,
  },
  {
    number: "03",
    shortTitle: "List & manage work",
    label: "Storefront & Orders",
    headline: "Sell products and manage incoming work from one workspace",
    body: "Publish ready-made goods, made-to-order pieces, and service rates. Convert incoming inquiries into tracked orders in one click and keep client measurements and notes organized.",
    previewEyebrow: "Active Workspace",
    previewTitle: "Products, Services & Work Inbox",
    previewSubtitle: "Everything organized on mobile or desktop",
    previewRows: [
      { label: "Catalog", value: "Ready-made goods & bespoke services", highlight: true },
      { label: "Inquiries", value: "1-click conversion to tracked order" },
      { label: "Client records", value: "Measurements, notes & order history" },
    ],
    icon: ShoppingBag,
  },
  {
    number: "04",
    shortTitle: "Deliver & get paid",
    label: "Reliable Settlement",
    headline: "Finish the job and receive direct bank payouts on time",
    body: "Start work knowing protected bookings are funded upfront. Mark the job complete once delivered and receive prompt settlement straight to your registered bank account.",
    previewEyebrow: "Payout Settled",
    previewTitle: "₦48,500.00 credited to bank",
    previewSubtitle: "Automatic ledger record upon customer sign-off",
    previewRows: [
      { label: "Status", value: "Settled to NUBAN account", highlight: true },
      { label: "Escrow fee", value: "Transparent 3% platform fee" },
      { label: "Ledger", value: "Exportable earnings history" },
    ],
    icon: CreditCard,
  },
];

export function HowItWorksFlow() {
  const [persona, setPersona] = useState<"customer" | "artisan">("customer");
  const [activeIndex, setActiveIndex] = useState(0);
  const [isInteracting, setIsInteracting] = useState(false);

  const steps = persona === "customer" ? CUSTOMER_STEPS : ARTISAN_STEPS;

  useEffect(() => {
    setActiveIndex(0);
  }, [persona]);

  useEffect(() => {
    if (isInteracting) return;
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % steps.length);
    }, 6000);
    return () => window.clearInterval(timer);
  }, [isInteracting, activeIndex, steps.length]);

  const connectorPct = (activeIndex / (steps.length - 1)) * 100;

  function goPrev() {
    setActiveIndex((prev) => (prev - 1 + steps.length) % steps.length);
  }

  function goNext() {
    setActiveIndex((prev) => (prev + 1) % steps.length);
  }

  return (
    <section
      id="how-it-works"
      className="relative overflow-hidden bg-plum py-20 text-white sm:py-24"
      onMouseEnter={() => setIsInteracting(true)}
      onMouseLeave={() => setIsInteracting(false)}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 top-12 h-80 w-80 rounded-full bg-brand-600/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 bottom-12 h-80 w-80 rounded-full bg-brand-500/15 blur-3xl"
      />

      <div className="relative mx-auto max-w-[1180px] px-5">
        {/* Heading + Persona Switcher */}
        <div className="mx-auto max-w-2xl text-center">
          <div className="mezer-eyebrow-light justify-center">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
            How It Works
          </div>
          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Simple from first search to final sign-off
          </h2>
          <p className="mt-3 text-base text-plum-soft">
            Select your role below to walk through how ArtisanOS connects neighborhoods with
            reliable local artisans.
          </p>

          <div className="mt-6 grid w-full max-w-sm grid-cols-2 gap-1.5 rounded-full border border-white/15 bg-white/[0.06] p-1.5 sm:mx-auto sm:inline-flex sm:w-auto sm:max-w-none">
            <button
              type="button"
              onClick={() => setPersona("customer")}
              className={`inline-flex items-center justify-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-bold transition-all duration-300 sm:gap-2 sm:px-5 sm:text-sm ${
                persona === "customer"
                  ? "bg-gradient-to-r from-brand-500 to-brand-700 text-white shadow-brand"
                  : "text-plum-soft hover:text-white"
              }`}
            >
              <UserCheck className="h-4 w-4 shrink-0" /> For Customers
            </button>
            <button
              type="button"
              onClick={() => setPersona("artisan")}
              className={`inline-flex items-center justify-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-bold transition-all duration-300 sm:gap-2 sm:px-5 sm:text-sm ${
                persona === "artisan"
                  ? "bg-gradient-to-r from-brand-500 to-brand-700 text-white shadow-brand"
                  : "text-plum-soft hover:text-white"
              }`}
            >
              <Store className="h-4 w-4 shrink-0" /> For Artisans
            </button>
          </div>
        </div>

        {/* Synchronized Horizontal Milestone Stepper Rail */}
        <div className="relative mx-auto mt-12 max-w-4xl">
          {/* Center-to-center rail track (Desktop) */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-[12.5%] right-[12.5%] top-6 hidden h-[2px] overflow-hidden rounded-full bg-white/15 sm:block"
          >
            <div
              className="relative h-full rounded-full bg-gradient-to-r from-brand-400 via-brand-500 to-brand-300 transition-[width] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
              style={{ width: `${connectorPct}%` }}
            >
              <span className="animate-flow-shimmer absolute inset-y-0 left-0 w-1/2 bg-gradient-to-r from-transparent via-white/80 to-transparent" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {steps.map((step, idx) => {
              const isActive = idx === activeIndex;
              const isCompleted = idx < activeIndex;
              return (
                <button
                  key={`${persona}-${step.number}`}
                  type="button"
                  onClick={() => setActiveIndex(idx)}
                  aria-current={isActive ? "step" : undefined}
                  className="group flex flex-col items-center text-center focus:outline-none"
                >
                  <span className="relative flex h-12 w-12 items-center justify-center">
                    {isActive && (
                      <span
                        aria-hidden="true"
                        className="animate-node-ring absolute inset-0 rounded-full border border-brand-400/70"
                      />
                    )}
                    <span
                      className={`relative z-10 flex h-12 w-12 items-center justify-center rounded-full border text-sm font-extrabold transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                        isActive
                          ? "scale-110 border-brand-300 bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand"
                          : isCompleted
                            ? "border-emerald-400/60 bg-emerald-500/20 text-emerald-200 group-hover:scale-105"
                            : "border-white/20 bg-plum-surface text-white/75 group-hover:border-white/40 group-hover:text-white"
                      }`}
                    >
                      {isCompleted ? <Check className="h-4 w-4" /> : step.number}
                    </span>
                  </span>

                  <span
                    className={`mt-3 text-xs font-bold transition-colors duration-300 sm:text-sm ${
                      isActive
                        ? "text-white"
                        : isCompleted
                          ? "text-emerald-200/90 group-hover:text-white"
                          : "text-plum-soft group-hover:text-white"
                    }`}
                  >
                    {step.shortTitle}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Smooth Hardware-Accelerated Horizontal Sliding Stage */}
        <div className="mt-8 overflow-hidden rounded-mezer-lg border border-white/15 bg-white/[0.06] backdrop-blur-md">
          <div
            className="flex transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] will-change-transform"
            style={{ transform: `translateX(-${activeIndex * 100}%)` }}
          >
            {steps.map((step, idx) => {
              const StepIcon = step.icon;
              const isFocused = idx === activeIndex;
              return (
                <div
                  key={`slide-${persona}-${step.number}`}
                  className="w-full shrink-0 p-4 sm:p-9 lg:p-10"
                >
                  <div
                    className={`grid items-center gap-6 transition-opacity duration-500 sm:gap-8 lg:grid-cols-[1.15fr_0.85fr] ${
                      isFocused ? "opacity-100" : "opacity-40"
                    }`}
                  >
                    {/* Left: Clear Step Explanation */}
                    <div className="space-y-3.5 sm:space-y-4">
                      <div className="inline-flex items-center gap-2 rounded-full bg-brand-500/20 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-[#ffdce6]">
                        <StepIcon className="h-3.5 w-3.5 shrink-0" />
                        Step {step.number} · {step.label}
                      </div>

                      <h3 className="text-xl font-extrabold leading-snug text-white sm:text-[1.7rem]">
                        {step.headline}
                      </h3>

                      <p className="max-w-xl text-sm leading-relaxed text-plum-soft sm:text-base">
                        {step.body}
                      </p>

                      <div className="pt-1 sm:pt-2">
                        <Link href={persona === "customer" ? "/marketplace" : "/register"}>
                          <Button size="sm" className="w-full sm:w-auto">
                            {persona === "customer"
                              ? "Explore nearby artisans"
                              : "Register your business"}
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Button>
                        </Link>
                      </div>
                    </div>

                    {/* Right: Structured Visual State Card */}
                    <div
                      className={`rounded-mezer-md border border-white/15 bg-plum/95 p-4 shadow-phone transition-transform duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] sm:p-6 ${
                        isFocused ? "translate-y-0 scale-100" : "translate-y-2 scale-[0.98]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-3.5">
                        <div className="min-w-0">
                          <div className="text-[11px] font-bold uppercase tracking-wider text-brand-300">
                            {step.previewEyebrow}
                          </div>
                          <div className="mt-1 break-words text-sm font-extrabold text-white sm:text-base">
                            {step.previewTitle}
                          </div>
                          <div className="text-xs text-plum-soft">{step.previewSubtitle}</div>
                        </div>
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-500/20 text-brand-300">
                          <StepIcon className="h-5 w-5" />
                        </div>
                      </div>

                      <div className="mt-4 space-y-2.5">
                        {step.previewRows.map((row) => (
                          <div
                            key={row.label}
                            className="flex flex-col gap-0.5 rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                          >
                            <span className="shrink-0 text-plum-soft">{row.label}</span>
                            <span
                              className={`inline-flex items-center gap-1 break-words font-bold sm:text-right ${
                                row.highlight ? "text-emerald-300" : "text-white"
                              }`}
                            >
                              {row.highlight && <BadgeCheck className="h-3.5 w-3.5 shrink-0" />}
                              {row.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Subtle Bottom Stage Navigation Bar */}
          <div className="flex items-center justify-between border-t border-white/10 bg-plum/40 px-6 py-3.5 sm:px-9">
            <div className="flex items-center gap-2">
              {steps.map((s, idx) => (
                <button
                  key={`dot-${s.number}`}
                  type="button"
                  aria-label={`Step ${s.number}: ${s.shortTitle}`}
                  onClick={() => setActiveIndex(idx)}
                  className={`h-1.5 rounded-full transition-all duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] ${
                    idx === activeIndex ? "w-9 bg-brand-400" : "w-2 bg-white/25 hover:bg-white/50"
                  }`}
                />
              ))}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={goPrev}
                aria-label="Previous step"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-white/[0.04] text-plum-soft transition-colors hover:border-white/30 hover:bg-white/10 hover:text-white"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={goNext}
                aria-label="Next step"
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-white/[0.04] text-plum-soft transition-colors hover:border-white/30 hover:bg-white/10 hover:text-white"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
