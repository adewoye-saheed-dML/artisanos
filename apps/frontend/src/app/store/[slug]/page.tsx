"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, MapPin, MessageCircle, Scissors, ShoppingBag, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatStatusLabel } from "@/lib/utils";
import type { Product, PublicStorefrontResponse } from "@/types/api";

export default function PublicStorefrontPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;

  const [typeFilter, setTypeFilter] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showInquiry, setShowInquiry] = useState(false);

  const [buyerName, setBuyerName] = useState("");
  const [buyerPhone, setBuyerPhone] = useState("");
  const [buyerEmail, setBuyerEmail] = useState("");
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
          buyer_name: buyerName,
          buyer_phone: buyerPhone,
          buyer_email: buyerEmail,
          message,
        }),
      }),
    onSuccess: () => {
      setInquiryError("");
      setInquirySent(true);
      setBuyerName("");
      setBuyerPhone("");
      setBuyerEmail("");
      setMessage("");
    },
    onError: (err) => {
      setInquiryError(err instanceof Error ? err.message : "Could not send inquiry.");
    },
  });

  const filteredProducts = (data?.products || []).filter((p) =>
    typeFilter ? p.product_type === typeFilter : true
  );

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[68px] max-w-[1180px] items-center justify-between px-5">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
              <Scissors className="h-4 w-4" />
            </div>
            <span className="text-sm font-extrabold tracking-tight text-plum">
              {data?.storefront.organization_name || "ArtisanOS Storefront"}
            </span>
          </Link>
          {data && (
            <Button
              size="sm"
              onClick={() => {
                setSelectedProduct(null);
                setInquirySent(false);
                setShowInquiry(true);
              }}
            >
              <MessageCircle className="h-4 w-4" />
              Contact artisan
            </Button>
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
                {error instanceof Error ? error.message : "This storefront is private or does not exist."}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {data && (
        <>
          {/* Velvet Plum Hero */}
          <section className="relative overflow-hidden bg-plum py-16 text-white">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-brand-500/25 blur-3xl"
            />
            <div className="relative mx-auto max-w-[1180px] px-5">
              <div className="mezer-eyebrow-light">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                <span className="capitalize">{data.storefront.category}</span> Storefront
              </div>
              <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-5xl">
                {data.storefront.organization_name}
              </h1>
              {data.storefront.headline && (
                <p className="mt-3 max-w-2xl text-lg text-[#ffdce6]">{data.storefront.headline}</p>
              )}
              {data.storefront.bio && (
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-plum-soft">
                  {data.storefront.bio}
                </p>
              )}
              <div className="mt-6 flex flex-wrap items-center gap-4 text-xs text-plum-soft">
                {(data.storefront.city || data.storefront.country) && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1">
                    <MapPin className="h-3.5 w-3.5 text-brand-300" />
                    {[data.storefront.city, data.storefront.country].filter(Boolean).join(", ")}
                  </span>
                )}
                {data.storefront.whatsapp_number && (
                  <span className="rounded-full bg-white/10 px-3 py-1">
                    WhatsApp: {data.storefront.whatsapp_number}
                  </span>
                )}
                {data.storefront.instagram_handle && (
                  <span className="rounded-full bg-white/10 px-3 py-1">
                    IG: {data.storefront.instagram_handle}
                  </span>
                )}
              </div>
            </div>
          </section>

          <main className="mx-auto max-w-[1180px] space-y-8 px-5 py-12">
            {/* Inquiry Panel */}
            {showInquiry && (
              <Card className="border-brand-300 rounded-mezer-lg">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <div className="mezer-eyebrow">Direct Inquiry</div>
                    <h2 className="mt-1 text-lg font-bold text-plum">
                      {selectedProduct
                        ? `Inquire about ${selectedProduct.name}`
                        : `Message ${data.storefront.organization_name}`}
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
                      <h3 className="mt-2 text-lg font-bold text-plum">Inquiry Sent</h3>
                      <p className="mt-1 text-sm text-ink-soft">
                        {data.storefront.organization_name} has been notified and will reach out to
                        you shortly.
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
                      <div>
                        <Label htmlFor="inq-msg">Message</Label>
                        <Textarea
                          id="inq-msg"
                          rows={3}
                          required
                          placeholder="Share your preferred fabric, size, or event date..."
                          value={message}
                          onChange={(e) => setMessage(e.target.value)}
                        />
                      </div>
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" onClick={() => setShowInquiry(false)}>
                          Cancel
                        </Button>
                        <Button type="submit" disabled={inquiryMutation.isPending}>
                          {inquiryMutation.isPending ? "Sending..." : "Send inquiry"}
                        </Button>
                      </div>
                    </form>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-extrabold tracking-tight text-plum">
                Collection ({filteredProducts.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {[
                  ["", "All"],
                  ["ready_made", "Ready-Made"],
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
                    Use &ldquo;Contact artisan&rdquo; above to inquire about custom orders.
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
                            {prod.stock_quantity > 0 ? `${prod.stock_quantity} in stock` : "Sold out"}
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
                    <div className="border-t border-line-soft px-6 py-4">
                      <Button
                        size="sm"
                        className="w-full"
                        onClick={() => {
                          setSelectedProduct(prod);
                          setInquirySent(false);
                          setShowInquiry(true);
                        }}
                      >
                        Inquire / Order this piece
                      </Button>
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
