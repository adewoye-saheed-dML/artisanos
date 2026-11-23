"use client";

import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  Lock,
  MapPin,
  Navigation,
  PhoneCall,
  Search,
  ShieldCheck,
  ShoppingBag,
  Store,
  UserCheck,
  Wrench,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { HowItWorksFlow } from "@/components/home/how-it-works-flow";
import {
  NigeriaLocationPicker,
  type NigeriaLocationValue,
} from "@/components/locations/nigeria-location-picker";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form-controls";
import { ARTISAN_CATEGORIES } from "@/lib/artisans";
import { useAuth } from "@/providers/auth-provider";

const FEATURED_TRADES = [
  {
    title: "Tailoring & Bespoke Fashion",
    subtitle:
      "Commission custom agbada, suits, dresses, and alterations, or shop ready-to-wear pieces directly from local workshops.",
    cta: "Browse tailors",
    href: "/marketplace?category=tailor",
    tag: "Custom & Ready-Made",
    image:
      "https://images.pexels.com/photos/34908665/pexels-photo-34908665/free-photo-of-close-up-of-sewing-machine-on-table.jpeg?auto=compress&cs=tinysrgb&w=900",
    alt: "Sewing machine and tailoring fabric materials arranged on a workshop table",
    objectPosition: "object-center",
  },
  {
    title: "Electrical Services",
    subtitle:
      "Book qualified electricians nearby for wiring diagnostics, distribution boards, solar inverters, and power installations.",
    cta: "Find electricians",
    href: "/marketplace?category=electrician",
    tag: "On-Site Service",
    image:
      "https://images.pexels.com/photos/12207608/pexels-photo-12207608.jpeg?auto=compress&cs=tinysrgb&w=900",
    alt: "Electrical control panel, wiring, and meter installation",
    objectPosition: "object-center",
  },
  {
    title: "Plumbing & Pipework",
    subtitle:
      "Get fast help for sink fittings, pipe leaks, bathroom installations, drainage repairs, and water pump maintenance.",
    cta: "Find plumbers",
    href: "/marketplace?category=plumber",
    tag: "Repairs & Fitting",
    image:
      "https://images.pexels.com/photos/14845870/pexels-photo-14845870.jpeg?auto=compress&cs=tinysrgb&w=900",
    alt: "Close-up of fitted plumbing pipes and joints installed along a wall",
    objectPosition: "object-center",
  },
  {
    title: "Carpentry & Custom Furniture",
    subtitle:
      "Work with skilled woodworkers for bespoke wardrobes, kitchen cabinets, doors, dining sets, and furniture restoration.",
    cta: "Find carpenters",
    href: "/marketplace?category=carpenter",
    tag: "Custom Woodwork",
    image:
      "https://images.pexels.com/photos/6790088/pexels-photo-6790088.jpeg?auto=compress&cs=tinysrgb&w=900",
    alt: "Carpenter shaping timber on a woodworking workbench",
    objectPosition: "object-center",
  },
];

const FAQ_ITEMS = [
  {
    q: "How does ArtisanOS verify artisans on the platform?",
    a: "Before an artisan storefront goes public, our compliance team reviews their government-issued National Identification Number (NIN), optional Corporate Affairs Commission (CAC) registration, guarantor details, and proof of address or workshop documents.",
  },
  {
    q: "How are customer payments protected until work is completed?",
    a: "When you book through our protected payment option, your funds are held safely in escrow and a private 6-digit completion code is generated for you. Full payment is only released to the artisan after you inspect the completed work and enter your code.",
  },
  {
    q: "Why does ArtisanOS organize search by Ward and Polling Unit?",
    a: "Searching by city alone often returns service providers miles away. By mapping Nigeria's 36 States, FCT Abuja, 774 LGAs, Electoral Wards, and Polling Units, ArtisanOS surfaces reliable professionals closest to your neighborhood first.",
  },
  {
    q: "Can I purchase finished products as well as book on-site services?",
    a: "Yes. You can browse ready-made clothing, handcrafted footwear, custom furniture, and other local goods directly from artisan storefronts, or book skilled professionals for home and office service visits.",
  },
];

const JSON_LD_SCHEMA = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "ArtisanOS Nigeria",
      url: "https://artisanos.ng",
      description:
        "Nigeria's neighborhood marketplace for hiring verified artisans by Ward and Polling Unit, buying handcrafted goods, and paying securely upon completion.",
      areaServed: { "@type": "Country", name: "Nigeria" },
    },
    {
      "@type": "WebSite",
      name: "ArtisanOS Nigeria",
      url: "https://artisanos.ng",
      potentialAction: {
        "@type": "SearchAction",
        target: "https://artisanos.ng/marketplace?search={search_term_string}",
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@type": "FAQPage",
      mainEntity: FAQ_ITEMS.map((item) => ({
        "@type": "Question",
        name: item.q,
        acceptedAnswer: {
          "@type": "Answer",
          text: item.a,
        },
      })),
    },
  ],
};

export default function HomePage() {
  const router = useRouter();
  const { user, activeOrganization, isLoading } = useAuth();

  const [category, setCategory] = useState("");
  const [keyword, setKeyword] = useState("");
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const [location, setLocation] = useState<NigeriaLocationValue>({
    stateId: "",
    lgaId: "",
    wardId: "",
    pollingUnitId: "",
  });

  useEffect(() => {
    const srcState = user?.state || activeOrganization?.state || "";
    const srcLga = user?.lga || activeOrganization?.lga || "";
    const srcWard = user?.ward || activeOrganization?.ward || "";
    const srcPu = user?.polling_unit || activeOrganization?.polling_unit || "";
    if ((srcState || srcLga || srcWard || srcPu) && !location.stateId && !location.wardId) {
      setLocation({
        stateId: srcState,
        lgaId: srcLga,
        wardId: srcWard,
        pollingUnitId: srcPu,
      });
    }
  }, [activeOrganization, location.stateId, location.wardId, user]);

  function handleNearbySearch(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (keyword.trim()) params.set("search", keyword.trim());
    if (location.stateId) params.set("state", location.stateId);
    if (location.lgaId) params.set("lga", location.lgaId);
    if (location.wardId) params.set("ward", location.wardId);
    if (location.pollingUnitId) params.set("polling_unit", location.pollingUnitId);
    router.push(`/marketplace?${params.toString()}`);
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* Structured SEO Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD_SCHEMA) }}
      />

      {/* Sticky Navigation */}
      <header className="sticky top-0 z-40 border-b border-line/80 bg-paper/90 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[72px] max-w-[1180px] items-center justify-between gap-4 px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
              <Wrench className="h-4 w-4" />
            </div>
            <span className="text-lg font-extrabold tracking-tight text-plum">ArtisanOS</span>
          </Link>

          <nav
            aria-label="Primary navigation"
            className="hidden items-center gap-7 text-sm font-medium text-ink-soft md:flex"
          >
            <Link href="/marketplace" className="font-bold text-brand-700 hover:underline">
              Marketplace
            </Link>
            <a href="#featured-trades" className="transition-colors hover:text-brand-700">
              Trades &amp; Goods
            </a>
            <a href="#how-it-works" className="transition-colors hover:text-brand-700">
              How It Works
            </a>
            <a href="#trust" className="transition-colors hover:text-brand-700">
              Trust &amp; Protection
            </a>
            <a href="#faq" className="transition-colors hover:text-brand-700">
              FAQ
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            {!isLoading && user ? (
              <Link href={user.memberships.length > 0 ? "/dashboard" : "/marketplace"}>
                <Button size="sm">
                  {user.memberships.length > 0 ? "Open workspace" : "Browse marketplace"}
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
                    Get started
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="mezer-hero-bg relative overflow-hidden pb-16 pt-10 sm:pb-22 sm:pt-14">
        <div
          aria-hidden="true"
          className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[520px] w-[520px] rounded-full"
        />

        <div className="relative mx-auto max-w-[1180px] space-y-10 px-5">
          <div className="grid items-center gap-10 lg:grid-cols-[1.08fr_0.92fr]">
            {/* Hero Copy */}
            <div className="animate-fade-up space-y-5">
              <div className="mezer-eyebrow">
                <Navigation className="h-3.5 w-3.5" />
                Across All 36 States, FCT Abuja &amp; 774 LGAs
              </div>

              <h1 className="text-4xl font-extrabold leading-[1.08] tracking-tight text-plum sm:text-5xl lg:text-[3.3rem]">
                Find skilled artisans right in your{" "}
                <span className="bg-gradient-to-r from-brand-500 to-brand-700 bg-clip-text text-transparent">
                  neighborhood.
                </span>
              </h1>

              <p className="max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
                Search verified tailors, electricians, plumbers, carpenters, mechanics, and local
                makers by Ward or Polling Unit. Hire directly for on-site work or purchase
                handcrafted goods with complete peace of mind.
              </p>

              <div className="flex flex-wrap items-center gap-3 pt-1">
                <a href="#nearby-search">
                  <Button size="lg">
                    <Search className="h-4 w-4" />
                    Find an Artisan
                  </Button>
                </a>
                <Link href="/register">
                  <Button variant="outline" size="lg">
                    <Store className="h-4 w-4" />
                    Register Your Business
                  </Button>
                </Link>
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-2 pt-1 text-xs font-semibold text-ink-soft">
                <span className="inline-flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-emerald-700" />
                  Vetted artisan profiles
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Lock className="h-4 w-4 text-brand-700" />
                  Protected milestone payments
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <PhoneCall className="h-4 w-4 text-brand-700" />
                  Direct phone &amp; WhatsApp contact
                </span>
              </div>
            </div>

            {/* Real Editorial Trade Photography Collage */}
            <div className="animate-fade-up relative">
              <div className="grid grid-cols-12 gap-3">
                {/* Main Real Workshop Photo */}
                <div className="relative col-span-12 aspect-[16/10] overflow-hidden rounded-mezer-lg border border-line bg-plum shadow-phone">
                  <Image
                    src="https://images.pexels.com/photos/3738095/pexels-photo-3738095.jpeg?auto=compress&cs=tinysrgb&w=1200"
                    alt="Tailor guiding fabric through a sewing machine in a bespoke workshop"
                    fill
                    priority
                    sizes="(max-width: 1024px) 100vw, 520px"
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-plum/80 via-plum/10 to-transparent" />
                  <div className="absolute bottom-3.5 left-4 right-4 text-white">
                    <div className="text-sm font-extrabold">Tailoring &amp; Bespoke Fashion</div>
                    <div className="text-xs text-plum-soft">
                      Local workshops ready for custom orders and finished pieces
                    </div>
                  </div>
                </div>

                {/* Two Matched Trade Sub-Photos */}
                <div className="relative col-span-6 aspect-[16/10] overflow-hidden rounded-mezer-md border border-line bg-plum shadow-card">
                  <Image
                    src="https://images.pexels.com/photos/12207608/pexels-photo-12207608.jpeg?auto=compress&cs=tinysrgb&w=800"
                    alt="Electrician testing electrical panel wiring with a multimeter"
                    fill
                    sizes="(max-width: 1024px) 50vw, 260px"
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-plum/75 via-transparent to-transparent" />
                  <div className="absolute bottom-2.5 left-3 text-xs font-bold text-white">
                    Electrical Services
                  </div>
                </div>

                <div className="relative col-span-6 aspect-[16/10] overflow-hidden rounded-mezer-md border border-line bg-plum shadow-card">
                  <Image
                    src="https://images.pexels.com/photos/6790088/pexels-photo-6790088.jpeg?auto=compress&cs=tinysrgb&w=800"
                    alt="Carpenter shaping timber with a planer in a woodworking workshop"
                    fill
                    sizes="(max-width: 1024px) 50vw, 260px"
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-plum/75 via-transparent to-transparent" />
                  <div className="absolute bottom-2.5 left-3 text-xs font-bold text-white">
                    Carpentry &amp; Woodwork
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Nearby Search Card */}
          <form
            id="nearby-search"
            onSubmit={handleNearbySearch}
            className="rounded-mezer-lg border border-line bg-white p-5 shadow-card sm:p-6"
          >
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-3">
              <div className="flex items-center gap-2 text-sm font-extrabold text-plum">
                <MapPin className="h-4 w-4 text-brand-700" />
                Search artisans and goods near your location
              </div>
              <span className="rounded-full bg-surface-blush px-3 py-0.5 text-[11px] font-bold text-brand-700">
                Ward &amp; Polling Unit Lookup
              </span>
            </div>

            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Select
                  aria-label="Select trade category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="mt-0 bg-white"
                >
                  <option value="">All Trades &amp; Services</option>
                  {ARTISAN_CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </Select>
                <Input
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="Search a service or item (e.g. inverter repair, sink leak, agbada, wardrobe)"
                  className="mt-0 bg-white"
                />
              </div>

              <NigeriaLocationPicker
                value={location}
                onChange={setLocation}
                compact
                allowCreateNew
                idPrefix="hero-loc"
              />

              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <p className="text-xs text-ink-soft">
                  Results are ranked by proximity—starting from your Polling Unit and Electoral Ward
                  outward.
                </p>
                <Button type="submit" size="lg" className="w-full sm:w-auto">
                  <Search className="h-4 w-4" />
                  Search Nearby
                </Button>
              </div>
            </div>
          </form>
        </div>
      </section>

      {/* Featured Trades Photographic Showcase */}
      <section id="featured-trades" className="border-y border-line-soft bg-surface py-16 sm:py-20">
        <div className="mx-auto max-w-[1180px] space-y-10 px-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-xl">
              <div className="mezer-eyebrow">Popular Categories</div>
              <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
                Services &amp; Handcrafted Goods Near You
              </h2>
              <p className="mt-2 text-sm text-ink-soft">
                Explore everyday trades and local makers ready to serve homes, offices, and
                businesses in your area.
              </p>
            </div>
            <Link href="/marketplace">
              <Button variant="outline" size="sm">
                View all categories <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURED_TRADES.map((card) => (
              <Link
                key={card.title}
                href={card.href}
                className="group flex flex-col overflow-hidden rounded-mezer-md border border-line bg-white shadow-mezer-sm transition-all duration-300 hover:-translate-y-1 hover:border-brand-300 hover:shadow-card-hover"
              >
                <div className="relative aspect-[4/3] w-full overflow-hidden bg-plum">
                  <Image
                    src={card.image}
                    alt={card.alt}
                    fill
                    sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 280px"
                    className={`object-cover ${card.objectPosition} transition-transform duration-500 group-hover:scale-105`}
                  />
                  <span className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-0.5 text-[10px] font-extrabold text-plum shadow-sm">
                    {card.tag}
                  </span>
                </div>
                <div className="flex flex-1 flex-col justify-between p-5">
                  <div>
                    <h3 className="text-base font-extrabold text-plum group-hover:text-brand-700">
                      {card.title}
                    </h3>
                    <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">{card.subtitle}</p>
                  </div>
                  <span className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-brand-700">
                    {card.cta}{" "}
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </div>
              </Link>
            ))}
          </div>

          {/* All Trade Quick-Links */}
          <div>
            <div className="mb-3 text-xs font-extrabold uppercase tracking-wider text-ink-faint">
              Browse by trade
            </div>
            <div className="flex flex-wrap gap-2">
              {ARTISAN_CATEGORIES.filter((c) => c.value !== "other").map((trade) => (
                <Link
                  key={trade.value}
                  href={`/marketplace?category=${trade.value}`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-4 py-2 text-xs font-bold text-plum transition-all hover:-translate-y-0.5 hover:border-brand-400 hover:bg-surface-blush hover:text-brand-700"
                >
                  {trade.shortLabel}
                  <ArrowRight className="h-3 w-3 text-ink-faint" />
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Animated How It Works Flow */}
      <HowItWorksFlow />

      {/* Trust & Protection Section */}
      <section id="trust" className="border-y border-line-soft bg-surface py-18 sm:py-22">
        <div className="mx-auto max-w-[1180px] px-5">
          <div className="mx-auto max-w-2xl text-center">
            <div className="mezer-eyebrow justify-center">
              <ShieldCheck className="h-3.5 w-3.5" />
              Trust &amp; Protection
            </div>
            <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-plum sm:text-4xl">
              Designed for accountability on both sides
            </h2>
            <p className="mt-2.5 text-sm text-ink-soft sm:text-base">
              Clear onboarding standards and protected payment milestones give customers and
              artisans a reliable way to work together.
            </p>
          </div>

          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            {/* For Customers */}
            <div className="rounded-mezer-lg border border-line bg-white p-7 shadow-card sm:p-8">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3.5 py-1 text-xs font-extrabold text-emerald-800">
                <UserCheck className="h-4 w-4" /> For Customers
              </div>
              <h3 className="mt-4 text-2xl font-extrabold text-plum">
                Hire locally and release payment upon completion.
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                Book vetted service providers near your address with the option to hold funds safely
                until you inspect and approve the finished work.
              </p>
              <ul className="mt-5 space-y-2.5 text-sm text-ink">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  <span>
                    Artisans complete identity screening (NIN, optional CAC registration, and
                    supporting documents) prior to listing.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  <span>
                    Search down to your Ward or Polling Unit for quicker response times and lower
                    transport fees.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  <span>
                    Protected escrow bookings release funds only after you confirm completion with
                    your private 6-digit code, with dispute review if needed.
                  </span>
                </li>
              </ul>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link href="/marketplace">
                  <Button>
                    Browse artisans <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
                <Link href="/escrow">
                  <Button variant="outline">
                    <Lock className="h-4 w-4" /> Payment protection
                  </Button>
                </Link>
              </div>
            </div>

            {/* For Artisans */}
            <div className="rounded-mezer-lg border border-line bg-white p-7 shadow-card sm:p-8">
              <div className="inline-flex items-center gap-2 rounded-full bg-surface-blush px-3.5 py-1 text-xs font-extrabold text-brand-700">
                <Store className="h-4 w-4" /> For Artisans &amp; Workshops
              </div>
              <h3 className="mt-4 text-2xl font-extrabold text-plum">
                Grow local demand and run your business in one place.
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                Put your craft in front of nearby customers, sell ready-made or bespoke products
                online, and keep orders and payouts organized.
              </p>
              <ul className="mt-5 space-y-2.5 text-sm text-ink">
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                  <span>
                    Stand out with a verified business profile that reassures new residential and
                    commercial clients.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                  <span>
                    Publish ready-made goods, custom orders, and service rates on your dedicated
                    storefront link.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                  <span>
                    Manage inquiries, customer records, measurements, and bank settlements from any
                    device.
                  </span>
                </li>
              </ul>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link href="/register">
                  <Button>
                    Register your business <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
                <Link href="/login">
                  <Button variant="outline">Sign in</Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="bg-paper py-16 sm:py-20">
        <div className="mx-auto max-w-3xl px-5">
          <div className="text-center">
            <div className="mezer-eyebrow justify-center">Frequently Asked Questions</div>
            <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Helpful answers before you begin
            </h2>
          </div>

          <div className="mt-8 space-y-3">
            {FAQ_ITEMS.map((item, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div
                  key={item.q}
                  className="overflow-hidden rounded-mezer-sm border border-line bg-white transition-colors"
                >
                  <button
                    type="button"
                    onClick={() => setOpenFaq(isOpen ? null : idx)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left text-sm font-bold text-plum hover:bg-surface"
                  >
                    <span>{item.q}</span>
                    <ChevronDown
                      className={`h-4 w-4 shrink-0 text-brand-700 transition-transform duration-200 ${
                        isOpen ? "rotate-180" : ""
                      }`}
                    />
                  </button>
                  {isOpen && (
                    <div className="border-t border-line-soft px-5 py-3.5 text-sm leading-relaxed text-ink-soft">
                      {item.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="mezer-hero-bg border-t border-line-soft py-16 text-center">
        <div className="mx-auto max-w-2xl px-5">
          <h2 className="text-3xl font-extrabold tracking-tight text-plum sm:text-4xl">
            Connect with trusted artisans in your area
          </h2>
          <p className="mt-3 text-base text-ink-soft">
            Serving neighborhoods across Lagos, Abuja, Port Harcourt, Ibadan, Kano, Enugu, and all
            36 States plus the FCT.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link href="/marketplace">
              <Button size="lg">
                <ShoppingBag className="h-4 w-4" /> Explore Marketplace
              </Button>
            </Link>
            <Link href="/register">
              <Button variant="outline" size="lg">
                Register Your Business
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-line bg-paper py-8">
        <div className="mx-auto flex max-w-[1180px] flex-col items-center justify-between gap-3 px-5 text-xs text-ink-faint sm:flex-row">
          <div className="flex items-center gap-2 font-semibold text-plum">
            <Wrench className="h-3.5 w-3.5 text-brand-700" />
            ArtisanOS Nigeria
          </div>
          <div>&copy; {new Date().getFullYear()} ArtisanOS Nigeria. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
