"use client";

import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Layers,
  Lock,
  Ruler,
  Scissors,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";

const WORKFLOW_STEPS = [
  {
    number: "01",
    title: "Capture or Request",
    body: "Record manual measurements in centimetres or inches, or send a secure expiring link so remote customers submit their own.",
    icon: Send,
  },
  {
    number: "02",
    title: "Review & Verify",
    body: "Every measurement is range-checked against configurable templates and verified by the artisan—never blindly trusted before cutting.",
    icon: CheckCircle2,
  },
  {
    number: "03",
    title: "Freeze & Produce",
    body: "Link a verified measurement profile to an order. When confirmed, ArtisanOS freezes a snapshot so future edits never overwrite past orders.",
    icon: ClipboardList,
  },
  {
    number: "04",
    title: "Scale Across Crafts",
    body: "Tailoring is built in today with 16 fields, while versioned templates let shoemakers and leatherworkers onboard without schema changes.",
    icon: Layers,
  },
];

const EXAMPLE_TEMPLATE_FIELDS = [
  { label: "Chest / Bust", range: "cm / in", required: true },
  { label: "Waist", range: "cm / in", required: true },
  { label: "Shoulder Width", range: "cm / in", required: true },
  { label: "Sleeve Length", range: "cm / in", required: true },
  { label: "Hip", range: "cm / in", required: true },
  { label: "Inseam & Outseam", range: "cm / in", required: false },
];

export default function HomePage() {
  const { user, isLoading } = useAuth();

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* Frosted sticky header */}
      <header className="sticky top-0 z-40 border-b border-line/80 bg-paper/90 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[72px] max-w-[1180px] items-center justify-between gap-4 px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
              <Scissors className="h-4 w-4" />
            </div>
            <span className="text-lg font-extrabold tracking-tight text-plum">ArtisanOS</span>
          </Link>

          <nav className="hidden items-center gap-7 text-sm font-medium text-ink-soft md:flex">
            <a href="#how-it-works" className="transition-colors hover:text-brand-700">
              How it works
            </a>
            <a href="#for-artisans" className="transition-colors hover:text-brand-700">
              For artisans
            </a>
            <a href="#transparency" className="transition-colors hover:text-brand-700">
              Privacy &amp; Fit
            </a>
            <Link href="/marketplace" className="font-semibold text-brand-700 hover:underline">
              Marketplace
            </Link>
          </nav>

          <div className="flex items-center gap-2.5">
            {!isLoading && user ? (
              <Link href="/dashboard">
                <Button size="sm">
                  Open dashboard
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            ) : (
              <>
                <Link href="/login">
                  <Button variant="ghost" size="sm">
                    Sign in
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="sm">
                    Start workspace
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="mezer-hero-bg relative overflow-hidden pb-20 pt-14 sm:pb-28 sm:pt-20">
        <div
          aria-hidden="true"
          className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[520px] w-[520px] rounded-full"
        />
        <div className="relative mx-auto grid max-w-[1180px] items-center gap-12 px-5 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16">
          <div className="space-y-6">
            <div className="mezer-eyebrow">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              Multi-Tenant Artisan SaaS
            </div>
            <h1 className="text-4xl font-extrabold leading-[1.08] tracking-tight text-plum sm:text-5xl lg:text-[3.4rem]">
              Your customers&apos; measurements. Your workshop.{" "}
              <span className="bg-gradient-to-r from-brand-500 to-brand-700 bg-clip-text text-transparent">
                Every fitting preserved.
              </span>
            </h1>
            <p className="max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
              ArtisanOS replaces scattered measurement notebooks with a versioned client fit book,
              secure customer measurement links, and order tracking built for bespoke tailors—and
              extensible to shoemakers and leatherworkers.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link href={user ? "/dashboard" : "/register"}>
                <Button size="lg">
                  {user ? "Go to your workspace" : "Create your tailor workspace"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href="#how-it-works">
                <Button variant="outline" size="lg">
                  See the workflow
                </Button>
              </a>
            </div>
            <div className="flex flex-wrap gap-5 pt-2 text-xs font-medium text-ink-faint">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-brand-700" />
                Tenant-isolated workspaces
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Ruler className="h-4 w-4 text-brand-700" />
                cm &amp; inches with history
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Lock className="h-4 w-4 text-brand-700" />
                Human-confirmed fit records
              </span>
            </div>
          </div>

          {/* Floating Fit Passport Card Visual */}
          <div className="relative mx-auto w-full max-w-md">
            <div className="relative rounded-mezer-lg border border-line bg-white p-6 shadow-phone">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-700 px-3.5 py-1 text-[11px] font-extrabold uppercase tracking-wider text-white shadow-brand">
                Standard Tailoring · v1
              </div>
              <div className="mt-2 flex items-center justify-between border-b border-line-soft pb-4">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    Configurable Fit Profile
                  </div>
                  <div className="mt-0.5 text-base font-bold text-plum">
                    16 Tailoring Measurements
                  </div>
                </div>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
                  Versioned
                </span>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2.5">
                {EXAMPLE_TEMPLATE_FIELDS.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-mezer-sm border border-line-soft bg-surface-blush px-3.5 py-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-ink">{item.label}</span>
                      {item.required && (
                        <span className="h-1.5 w-1.5 rounded-full bg-brand-500" title="Required" />
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-ink-faint">Unit: {item.range}</div>
                  </div>
                ))}
              </div>

              <div className="mt-5 rounded-mezer-sm bg-plum px-4 py-3.5 text-white">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#ffdce6]">Order Snapshot Guarantee</span>
                  <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-300">
                    Immutable
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-relaxed text-plum-soft">
                  Editing a client&apos;s fit later creates a new version—confirmed orders always keep
                  their exact cut-time measurements.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Dark Velvet Plum Workflow Section */}
      <section id="how-it-works" className="bg-plum py-20 text-white sm:py-24">
        <div className="mx-auto max-w-[1180px] px-5">
          <div className="mx-auto max-w-2xl text-center">
            <div className="mezer-eyebrow-light justify-center">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              How ArtisanOS Works
            </div>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              Serve customers beyond your fitting room.
            </h2>
            <p className="mt-3 text-base text-plum-soft">
              A clean four-stage workflow from first measurement to final fitting—built around real
              workshop operations.
            </p>
          </div>

          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {WORKFLOW_STEPS.map((step) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.number}
                  className="group flex flex-col rounded-mezer-md border border-white/10 bg-white/[0.04] p-7 backdrop-blur-sm transition-all duration-200 hover:-translate-y-1 hover:border-brand-500/50 hover:bg-white/[0.07]"
                >
                  <div className="mb-6 flex items-center justify-between">
                    <span className="grid h-11 w-11 place-items-center rounded-full border border-brand-500 bg-brand-500/15 text-sm font-extrabold text-white">
                      {step.number}
                    </span>
                    <Icon className="h-5 w-5 text-brand-300" />
                  </div>
                  <h3 className="text-lg font-bold text-white">{step.title}</h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-plum-soft">{step.body}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Expectations & Transparency Section */}
      <section
        id="transparency"
        className="border-y border-line-soft bg-surface py-20 sm:py-24"
      >
        <div className="mx-auto max-w-[1180px] px-5">
          <div className="grid items-center gap-10 rounded-mezer-lg border border-line bg-white p-8 shadow-card sm:p-12 lg:grid-cols-[0.95fr_1.05fr]">
            <div>
              <div className="mezer-eyebrow">
                <Sparkles className="h-3.5 w-3.5" />
                Technology With Transparency
              </div>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-plum">
                Human-confirmed fit first. Privacy by design.
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-ink-soft sm:text-base">
                Great tailoring relies on accurate numbers, not inflated promises. ArtisanOS puts
                structured records, consent, and audit history first—and keeps future camera-assisted
                capture clearly gated until independently validated.
              </p>
            </div>

            <div id="for-artisans" className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  title: "Explicit Customer Consent",
                  desc: "Public measurement request links expire automatically, prevent reuse, and record explicit consent.",
                },
                {
                  title: "Strict Multi-Tenant Isolation",
                  desc: "Every customer, profile, and order is scoped server-side to verified workspace memberships.",
                },
                {
                  title: "Configurable Vertical Templates",
                  desc: "Tailoring and shoemaking templates live in the database—create custom schemas anytime.",
                },
                {
                  title: "Auditable Order Timeline",
                  desc: "Validated status transitions track every garment from draft and quote to fitting and collection.",
                },
              ].map((card) => (
                <div
                  key={card.title}
                  className="flex flex-col justify-between rounded-mezer-sm border border-line bg-surface p-5 transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-mezer-sm"
                >
                  <h3 className="text-sm font-bold text-plum">{card.title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-ink-soft">{card.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="mezer-hero-bg py-20 text-center">
        <div className="mx-auto max-w-2xl px-5">
          <h2 className="text-3xl font-extrabold tracking-tight text-plum sm:text-4xl">
            Craftsmanship shouldn&apos;t be limited by paper books.
          </h2>
          <p className="mt-3 text-base text-ink-soft">
            Launch your isolated ArtisanOS workspace and record your first customer measurement in
            under a minute.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link href={user ? "/dashboard" : "/register"}>
              <Button size="lg">
                {user ? "Open dashboard" : "Create free workspace"}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button variant="outline" size="lg">
                Sign in
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-line bg-paper py-8">
        <div className="mx-auto flex max-w-[1180px] flex-col items-center justify-between gap-3 px-5 text-xs text-ink-faint sm:flex-row">
          <div className="flex items-center gap-2 font-semibold text-plum">
            <Scissors className="h-3.5 w-3.5 text-brand-700" />
            ArtisanOS · Multi-Tenant Measurement &amp; Order Platform
          </div>
          <div>Tailoring MVP · Configurable templates for artisan businesses</div>
        </div>
      </footer>
    </div>
  );
}
