"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, MapPin, Scissors, Search, ShoppingBag, Store } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatStatusLabel } from "@/lib/utils";
import type { MarketplaceProductCard, MarketplaceStorefrontCard } from "@/types/api";

export default function MarketplacePage() {
  const [tab, setTab] = useState<"storefronts" | "products">("storefronts");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");

  const { data: storefronts, isLoading: loadingStores } = useQuery({
    queryKey: ["marketplace-storefronts", search, category],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (category) params.set("category", category);
      return apiRequest<MarketplaceStorefrontCard[]>(
        `/marketplace/storefronts/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
  });

  const { data: products, isLoading: loadingProducts } = useQuery({
    queryKey: ["marketplace-products", search, category],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (category) params.set("category", category);
      return apiRequest<MarketplaceProductCard[]>(
        `/marketplace/products/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
  });

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[70px] max-w-[1180px] items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
              <Scissors className="h-4 w-4" />
            </div>
            <span className="text-base font-extrabold tracking-tight text-plum">
              ArtisanOS Marketplace
            </span>
          </Link>
          <div className="flex items-center gap-2.5">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/register">
              <Button size="sm">Open your storefront</Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="mezer-hero-bg relative overflow-hidden border-b border-line-soft py-14">
        <div
          aria-hidden="true"
          className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[440px] w-[440px] rounded-full"
        />
        <div className="relative mx-auto max-w-[1180px] space-y-6 px-5">
          <div>
            <div className="mezer-eyebrow">Discover Independent Craft</div>
            <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-plum sm:text-5xl">
              Explore Bespoke Tailors, Shoemakers &amp; Leather Artisans
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-ink-soft sm:text-base">
              Browse live published storefronts and ready-made or made-to-order pieces directly from
              ArtisanOS workshops.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-ink-faint" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search ateliers, garments, shoes, leather goods..."
                className="mt-0 rounded-full bg-white pl-10 shadow-mezer-sm"
              />
            </div>
            <Select
              aria-label="Filter artisan category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="mt-0 rounded-full bg-white shadow-mezer-sm sm:w-52"
            >
              <option value="">All artisan crafts</option>
              <option value="tailor">Tailors</option>
              <option value="shoemaker">Shoemakers</option>
              <option value="leatherworker">Leatherworkers</option>
              <option value="other">Other</option>
            </Select>
          </div>

          <div className="inline-flex rounded-full border border-line bg-white p-1 shadow-mezer-sm">
            <button
              type="button"
              onClick={() => setTab("storefronts")}
              className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-colors ${
                tab === "storefronts" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
              }`}
            >
              <Store className="h-3.5 w-3.5" /> Storefronts ({storefronts?.length ?? 0})
            </button>
            <button
              type="button"
              onClick={() => setTab("products")}
              className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition-colors ${
                tab === "products" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
              }`}
            >
              <ShoppingBag className="h-3.5 w-3.5" /> Products ({products?.length ?? 0})
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-[1180px] px-5 py-12">
        {tab === "storefronts" && (
          <>
            {loadingStores && <Card className="h-48 animate-pulse bg-surface" />}
            {!loadingStores && !storefronts?.length ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <Store className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">No storefronts match yet</h2>
                  <p className="mt-1 text-sm text-ink-soft">
                    Publish your storefront inside your workspace to appear here.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {storefronts?.map((sf) => (
                  <Card
                    key={sf.slug}
                    className="flex flex-col justify-between transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
                  >
                    <CardContent className="space-y-3 p-6">
                      <div className="flex items-center justify-between">
                        <span className="rounded-full bg-surface-blush px-3 py-0.5 text-[11px] font-bold capitalize text-brand-700">
                          {sf.category}
                        </span>
                        <span className="text-xs font-semibold text-ink-faint">
                          {sf.published_product_count}{" "}
                          {sf.published_product_count === 1 ? "listing" : "listings"}
                        </span>
                      </div>
                      <h2 className="text-lg font-extrabold text-plum">{sf.organization_name}</h2>
                      {sf.headline && <p className="text-sm text-ink-soft">{sf.headline}</p>}
                      {(sf.city || sf.country) && (
                        <div className="flex items-center gap-1 text-xs text-ink-faint">
                          <MapPin className="h-3.5 w-3.5 text-brand-600" />
                          {[sf.city, sf.country].filter(Boolean).join(", ")}
                        </div>
                      )}
                    </CardContent>
                    <div className="border-t border-line-soft px-6 py-4">
                      <Link href={`/store/${sf.slug}`}>
                        <Button size="sm" variant="outline" className="w-full">
                          Visit storefront <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "products" && (
          <>
            {loadingProducts && <Card className="h-48 animate-pulse bg-surface" />}
            {!loadingProducts && !products?.length ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <ShoppingBag className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">No published products yet</h2>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {products?.map((p) => (
                  <Card
                    key={p.id}
                    className="flex flex-col justify-between transition-all hover:-translate-y-0.5 hover:shadow-card-hover"
                  >
                    <CardContent className="space-y-2.5 p-6">
                      <div className="flex items-center justify-between">
                        <span className="rounded-full bg-surface-blush px-3 py-0.5 text-[11px] font-bold text-brand-700">
                          {formatStatusLabel(p.product_type)}
                        </span>
                        <span className="text-xs text-ink-faint">{p.organization_city}</span>
                      </div>
                      <h2 className="text-lg font-bold text-plum">{p.name}</h2>
                      <div className="text-xs font-semibold text-ink-soft">
                        by {p.organization_name}
                      </div>
                      <div className="pt-1 text-xl font-extrabold text-plum">
                        {formatCurrency(p.price, p.currency)}
                      </div>
                    </CardContent>
                    <div className="border-t border-line-soft px-6 py-4">
                      <Link href={`/store/${p.storefront_slug}`}>
                        <Button size="sm" className="w-full">
                          View &amp; inquire <ArrowRight className="h-3.5 w-3.5" />
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
