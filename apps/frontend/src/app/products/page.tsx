"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightCircle,
  ArrowUpDown,
  ClipboardCopy,
  ExternalLink,
  History,
  Inbox,
  MapPin,
  MessageCircle,
  Package,
  Phone,
  Plus,
  Store,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import {
  buildTelHref,
  buildWhatsAppHref,
  getDefaultProductCategory,
} from "@/lib/artisans";
import { formatCurrency, formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  InquiryStatus,
  InventoryMovement,
  InventoryMovementType,
  OrderDetail,
  PaginatedResponse,
  Product,
  ProductStatus,
  ProductType,
  StorefrontInquiry,
  StorefrontSettings,
} from "@/types/api";

export default function ProductsPage() {
  const { activeOrganization, activeMembership } = useAuth();
  const queryClient = useQueryClient();
  const canManageStore =
    activeMembership?.role === "owner" || activeMembership?.role === "manager";

  const [tab, setTab] = useState<"catalogue" | "inquiries">("catalogue");
  const [typeFilter, setTypeFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showStorefrontEdit, setShowStorefrontEdit] = useState(false);

  // Create product state
  const [name, setName] = useState("");
  const [category, setCategory] = useState(getDefaultProductCategory(activeOrganization?.category));
  const [productType, setProductType] = useState<ProductType>("ready_made");
  const [price, setPrice] = useState("25000.00");
  const [sku, setSku] = useState("");
  const [initialStock, setInitialStock] = useState("5");
  const [status, setStatus] = useState<ProductStatus>("published");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState("");
  const [convertNotice, setConvertNotice] = useState("");

  // Inventory adjust & ledger state
  const [adjustingProduct, setAdjustingProduct] = useState<Product | null>(null);
  const [movementType, setMovementType] = useState<InventoryMovementType>("restock");
  const [deltaInput, setDeltaInput] = useState("1");
  const [reasonInput, setReasonInput] = useState("");
  const [adjustError, setAdjustError] = useState("");
  const [ledgerProduct, setLedgerProduct] = useState<Product | null>(null);

  // Storefront settings state
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [instagram, setInstagram] = useState("");
  const [sfPublished, setSfPublished] = useState(true);
  const [sfMessage, setSfMessage] = useState("");

  const { data: storefront } = useQuery({
    queryKey: ["storefront-settings", activeOrganization?.id],
    queryFn: () => apiRequest<StorefrontSettings>("/storefront/settings/"),
    enabled: !!activeOrganization?.id,
  });

  useEffect(() => {
    if (storefront) {
      setHeadline(storefront.headline);
      setBio(storefront.bio);
      setWhatsapp(storefront.whatsapp_number);
      setInstagram(storefront.instagram_handle);
      setSfPublished(storefront.is_published);
    }
  }, [storefront]);

  const { data: productsData, isLoading: loadingProducts } = useQuery({
    queryKey: ["products", activeOrganization?.id, typeFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (typeFilter) params.set("product_type", typeFilter);
      return apiRequest<PaginatedResponse<Product>>(`/products/?${params.toString()}`);
    },
    enabled: !!activeOrganization?.id,
  });

  const { data: inquiriesData } = useQuery({
    queryKey: ["storefront-inquiries", activeOrganization?.id],
    queryFn: () => apiRequest<PaginatedResponse<StorefrontInquiry>>("/storefront/inquiries/"),
    enabled: !!activeOrganization?.id,
  });

  const { data: movementsData } = useQuery({
    queryKey: ["product-movements", activeOrganization?.id, ledgerProduct?.id],
    queryFn: () => apiRequest<InventoryMovement[]>(`/products/${ledgerProduct?.id}/movements/`),
    enabled: !!activeOrganization?.id && !!ledgerProduct?.id,
  });

  const createProductMutation = useMutation({
    mutationFn: () =>
      apiRequest<Product>("/products/", {
        method: "POST",
        body: JSON.stringify({
          name,
          category,
          product_type: productType,
          price,
          sku,
          status,
          description,
          track_inventory: productType === "ready_made",
          initial_stock: productType === "ready_made" ? Number(initialStock) || 0 : 0,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setName("");
      setSku("");
      setDescription("");
      setShowCreate(false);
      setFormError("");
    },
    onError: (err) => {
      setFormError(err instanceof Error ? err.message : "Could not create product.");
    },
  });

  const updateProductStatusMutation = useMutation({
    mutationFn: ({ id, nextStatus }: { id: string; nextStatus: ProductStatus }) =>
      apiRequest<Product>(`/products/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  const adjustInventoryMutation = useMutation({
    mutationFn: () => {
      if (!adjustingProduct) throw new Error("No product selected.");
      let delta = Math.abs(Number(deltaInput) || 0);
      if (movementType === "sale" || movementType === "damage") {
        delta = -delta;
      } else if (movementType === "adjustment") {
        delta = Number(deltaInput) || 0;
      }
      return apiRequest<InventoryMovement>(`/products/${adjustingProduct.id}/adjust-inventory/`, {
        method: "POST",
        body: JSON.stringify({
          movement_type: movementType,
          quantity_delta: delta,
          reason: reasonInput,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["product-movements"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-badge"] });
      setAdjustingProduct(null);
      setReasonInput("");
      setDeltaInput("1");
      setAdjustError("");
    },
    onError: (err) => {
      setAdjustError(err instanceof Error ? err.message : "Could not adjust stock.");
    },
  });

  const updateStorefrontMutation = useMutation({
    mutationFn: () =>
      apiRequest<StorefrontSettings>("/storefront/settings/", {
        method: "PATCH",
        body: JSON.stringify({
          headline,
          bio,
          whatsapp_number: whatsapp,
          instagram_handle: instagram,
          is_published: sfPublished,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storefront-settings"] });
      setSfMessage("Storefront profile updated.");
      setShowStorefrontEdit(false);
    },
  });

  const updateInquiryMutation = useMutation({
    mutationFn: ({ id, nextStatus }: { id: string; nextStatus: InquiryStatus }) =>
      apiRequest(`/storefront/inquiries/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storefront-inquiries"] });
    },
  });

  const convertInquiryMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest<OrderDetail>(`/storefront/inquiries/${id}/convert/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ["storefront-inquiries"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      setConvertNotice(`Converted into Order ${order.order_number} for ${order.customer_name}.`);
    },
    onError: (err) => {
      setConvertNotice(err instanceof Error ? err.message : "Could not convert inquiry.");
    },
  });

  const publicStorePath = `/store/${storefront?.slug || activeOrganization?.slug || ""}`;
  const newInquiryCount =
    inquiriesData?.results.filter((i) => i.status === "new").length ?? 0;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Velvet Plum Storefront Banner */}
        <div className="relative overflow-hidden rounded-mezer-lg bg-plum px-6 py-6 text-white shadow-card sm:px-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full bg-brand-500/20 blur-3xl"
          />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="mezer-eyebrow-light">
                <Store className="h-3.5 w-3.5 text-brand-300" />
                Public Storefront &amp; Inventory
              </div>
              <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-white">
                Products &amp; Storefront
              </h1>
              <p className="mt-1 text-xs text-plum-soft">
                Public storefront:{" "}
                <span className="font-mono text-[#ffdce6]">{publicStorePath}</span>{" "}
                · {storefront?.is_published ? "Published" : "Unpublished"}
                {storefront?.ward_name
                  ? ` · Pinned to ${storefront.ward_name}${storefront.polling_unit_name ? ` (${storefront.polling_unit_name})` : ""}`
                  : " · Pin your Ward & Polling Unit in Workspace Settings to appear in nearby searches"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href={publicStorePath} target="_blank">
                <Button variant="light" size="sm">
                  <ExternalLink className="h-3.5 w-3.5" />
                  View storefront
                </Button>
              </Link>
              <Button
                variant="outline"
                size="sm"
                className="border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                onClick={() => {
                  if (typeof window !== "undefined") {
                    navigator.clipboard?.writeText(`${window.location.origin}${publicStorePath}`);
                  }
                }}
              >
                <ClipboardCopy className="h-3.5 w-3.5" />
                Copy URL
              </Button>
              {canManageStore && (
                <Button
                  size="sm"
                  onClick={() => setShowStorefrontEdit((v) => !v)}
                >
                  Edit storefront
                </Button>
              )}
            </div>
          </div>
        </div>

        {sfMessage && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
            {sfMessage}
          </div>
        )}

        {showStorefrontEdit && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <h2 className="text-base font-bold text-plum">Public Storefront Profile</h2>
              <Button size="sm" variant="ghost" onClick={() => setShowStorefrontEdit(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="sf-headline">Headline</Label>
                  <Input
                    id="sf-headline"
                    value={headline}
                    onChange={(e) => setHeadline(e.target.value)}
                    placeholder="Bespoke tailoring crafted in Lagos"
                  />
                </div>
                <div>
                  <Label htmlFor="sf-whatsapp">WhatsApp / Contact Number</Label>
                  <Input
                    id="sf-whatsapp"
                    value={whatsapp}
                    onChange={(e) => setWhatsapp(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="sf-ig">Instagram handle (optional)</Label>
                  <Input
                    id="sf-ig"
                    placeholder="@youratelier"
                    value={instagram}
                    onChange={(e) => setInstagram(e.target.value)}
                  />
                </div>
                <div className="flex items-end pb-2">
                  <label className="flex items-center gap-2 text-sm font-semibold text-plum">
                    <input
                      type="checkbox"
                      className="accent-brand-700"
                      checked={sfPublished}
                      onChange={(e) => setSfPublished(e.target.checked)}
                    />
                    Storefront publicly visible
                  </label>
                </div>
              </div>
              <div>
                <Label htmlFor="sf-bio">Workshop story / bio</Label>
                <Textarea id="sf-bio" rows={2} value={bio} onChange={(e) => setBio(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowStorefrontEdit(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={() => updateStorefrontMutation.mutate()}
                  disabled={updateStorefrontMutation.isPending}
                >
                  Save storefront
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tabs & Action Row */}
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <div className="flex w-full rounded-full border border-line bg-white p-1 shadow-mezer-sm sm:inline-flex sm:w-auto">
            <button
              type="button"
              onClick={() => setTab("catalogue")}
              className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors sm:flex-initial sm:px-4 ${
                tab === "catalogue" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
              }`}
            >
              <Package className="h-3.5 w-3.5" /> Catalogue
            </button>
            <button
              type="button"
              onClick={() => setTab("inquiries")}
              className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors sm:flex-initial sm:px-4 ${
                tab === "inquiries" ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
              }`}
            >
              <Inbox className="h-3.5 w-3.5" />
              <span className="truncate">Calls &amp; Inquiries</span>
              {newInquiryCount > 0 && (
                <span className="rounded-full bg-brand-500 px-1.5 py-0.5 text-[10px] font-extrabold text-white">
                  {newInquiryCount}
                </span>
              )}
            </button>
          </div>

          {tab === "catalogue" && (
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
              <Select
                aria-label="Filter product type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="mt-0 w-full rounded-full bg-white py-2 text-xs shadow-mezer-sm sm:w-44"
              >
                <option value="">All listing types</option>
                <option value="ready_made">Ready-Made</option>
                <option value="made_to_order">Made to Order</option>
                <option value="service">Service Listing</option>
              </Select>
              <Button size="sm" className="w-full sm:w-auto" onClick={() => setShowCreate((v) => !v)}>
                {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {showCreate ? "Close" : "Add product"}
              </Button>
            </div>
          )}
        </div>

        {/* Create Product Form */}
        {tab === "catalogue" && showCreate && (
          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">New Product or Service Listing</h2>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  createProductMutation.mutate();
                }}
              >
                {formError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {formError}
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="sm:col-span-2">
                    <Label htmlFor="prod-name">Product name</Label>
                    <Input
                      id="prod-name"
                      required
                      placeholder="e.g. Tailored Linen Kaftan"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="prod-type">Listing type</Label>
                    <Select
                      id="prod-type"
                      value={productType}
                      onChange={(e) => setProductType(e.target.value as ProductType)}
                    >
                      <option value="ready_made">Ready-Made (Tracked Stock)</option>
                      <option value="made_to_order">Made to Order</option>
                      <option value="service">Service Listing</option>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-4">
                  <div>
                    <Label htmlFor="prod-price">Price ({activeOrganization?.currency})</Label>
                    <Input
                      id="prod-price"
                      type="number"
                      step="0.01"
                      min="0"
                      required
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="prod-cat">Category</Label>
                    <Input
                      id="prod-cat"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="prod-status">Publication status</Label>
                    <Select
                      id="prod-status"
                      value={status}
                      onChange={(e) => setStatus(e.target.value as ProductStatus)}
                    >
                      <option value="published">Published (Live on store)</option>
                      <option value="draft">Draft (Hidden)</option>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="prod-stock">
                      {productType === "ready_made" ? "Initial stock qty" : "SKU (optional)"}
                    </Label>
                    {productType === "ready_made" ? (
                      <Input
                        id="prod-stock"
                        type="number"
                        min={0}
                        value={initialStock}
                        onChange={(e) => setInitialStock(e.target.value)}
                      />
                    ) : (
                      <Input
                        id="prod-stock"
                        placeholder="SKU-001"
                        value={sku}
                        onChange={(e) => setSku(e.target.value)}
                      />
                    )}
                  </div>
                </div>
                <div>
                  <Label htmlFor="prod-desc">Description</Label>
                  <Textarea
                    id="prod-desc"
                    rows={2}
                    placeholder="Fabric details, turnaround time, sizing notes..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCreate(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createProductMutation.isPending}>
                    {createProductMutation.isPending ? "Saving..." : "Save listing"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Inventory Adjustment Panel */}
        {adjustingProduct && (
          <Card className="border-brand-300">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-plum">
                  Adjust Stock · {adjustingProduct.name}
                </h2>
                <p className="text-xs text-ink-faint">
                  Current stock: <strong>{adjustingProduct.stock_quantity}</strong>. Every adjustment
                  is permanently recorded in the inventory ledger.
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setAdjustingProduct(null)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <form
                className="grid gap-4 sm:grid-cols-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  adjustInventoryMutation.mutate();
                }}
              >
                {adjustError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 sm:col-span-4">
                    {adjustError}
                  </div>
                )}
                <div>
                  <Label htmlFor="adj-type">Movement type</Label>
                  <Select
                    id="adj-type"
                    value={movementType}
                    onChange={(e) => setMovementType(e.target.value as InventoryMovementType)}
                  >
                    <option value="restock">Restock (+)</option>
                    <option value="sale">Sale (-)</option>
                    <option value="return">Customer Return (+)</option>
                    <option value="damage">Damage / Write-off (-)</option>
                    <option value="adjustment">Manual Adjustment (+/-)</option>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="adj-qty">Quantity</Label>
                  <Input
                    id="adj-qty"
                    type="number"
                    required
                    value={deltaInput}
                    onChange={(e) => setDeltaInput(e.target.value)}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label htmlFor="adj-reason">Audit reason</Label>
                  <Input
                    id="adj-reason"
                    required
                    placeholder="e.g. New batch finished, studio walk-in sale"
                    value={reasonInput}
                    onChange={(e) => setReasonInput(e.target.value)}
                  />
                </div>
                <div className="flex justify-end gap-2 sm:col-span-4">
                  <Button variant="outline" onClick={() => setAdjustingProduct(null)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={adjustInventoryMutation.isPending}>
                    Record stock movement
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Inventory Movement Ledger Modal/Card */}
        {ledgerProduct && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-brand-700" />
                <h2 className="text-base font-bold text-plum">
                  Inventory Ledger · {ledgerProduct.name}
                </h2>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setLedgerProduct(null)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="divide-y divide-line-soft p-0">
              {!movementsData?.length ? (
                <p className="p-6 text-sm text-ink-faint">No stock movements recorded yet.</p>
              ) : (
                movementsData.map((m) => (
                  <div key={m.id} className="flex flex-wrap items-center justify-between gap-2 px-6 py-3.5">
                    <div>
                      <div className="text-sm font-semibold text-plum">
                        {formatStatusLabel(m.movement_type)} ·{" "}
                        <span className={m.quantity_delta >= 0 ? "text-emerald-700" : "text-red-600"}>
                          {m.quantity_delta >= 0 ? `+${m.quantity_delta}` : m.quantity_delta}
                        </span>
                      </div>
                      <div className="text-xs text-ink-soft">
                        {m.reason} {m.performed_by_name ? `· by ${m.performed_by_name}` : ""}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-bold text-plum">Balance: {m.balance_after}</div>
                      <div className="text-[11px] text-ink-faint">{formatDateTime(m.created_at)}</div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        )}

        {/* Catalogue Grid */}
        {tab === "catalogue" && (
          <>
            {loadingProducts && <Card className="h-48 animate-pulse bg-white/70" />}
            {productsData && productsData.results.length === 0 ? (
              <Card className="border-dashed border-brand-200 bg-surface-blush">
                <CardContent className="py-12 text-center">
                  <Package className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">No products listed yet</h2>
                  <p className="mt-1 text-sm text-ink-soft">
                    Add ready-made garments, bespoke made-to-order pieces, or tailoring services to
                    populate your public storefront.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
                {productsData?.results.map((prod) => (
                  <Card key={prod.id} className="flex flex-col justify-between">
                    <CardContent className="space-y-3 p-5">
                      <div className="flex items-start justify-between gap-2">
                        <span className="rounded-full bg-surface-blush px-2.5 py-0.5 text-[11px] font-bold text-brand-700">
                          {formatStatusLabel(prod.product_type)}
                        </span>
                        <StatusBadge status={prod.status} />
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-plum">{prod.name}</h3>
                        <p className="text-xs text-ink-faint">{prod.category}</p>
                      </div>
                      {prod.description && (
                        <p className="line-clamp-2 text-xs leading-relaxed text-ink-soft">
                          {prod.description}
                        </p>
                      )}
                      <div className="flex items-baseline justify-between pt-1">
                        <span className="text-lg font-extrabold text-plum">
                          {formatCurrency(prod.price, prod.currency)}
                        </span>
                        {prod.track_inventory && (
                          <span
                            className={`text-xs font-bold ${
                              prod.stock_quantity <= 2 ? "text-amber-700" : "text-emerald-700"
                            }`}
                          >
                            Stock: {prod.stock_quantity}
                          </span>
                        )}
                      </div>
                    </CardContent>
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line-soft px-5 py-3">
                      <div className="flex gap-1.5">
                        {prod.track_inventory && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setAdjustingProduct(prod);
                                setAdjustError("");
                              }}
                            >
                              <ArrowUpDown className="h-3.5 w-3.5" />
                              Stock
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setLedgerProduct(prod)}
                            >
                              Ledger
                            </Button>
                          </>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                          updateProductStatusMutation.mutate({
                            id: prod.id,
                            nextStatus: prod.status === "published" ? "draft" : "published",
                          })
                        }
                      >
                        {prod.status === "published" ? "Unpublish" : "Publish"}
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}

        {/* Storefront Work Calls & Inquiries Tab */}
        {tab === "inquiries" && (
          <div className="space-y-4">
            {convertNotice && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
                {convertNotice}
              </div>
            )}
            <Card className="overflow-hidden">
              {!inquiriesData?.results.length ? (
                <CardContent className="py-12 text-center">
                  <Inbox className="mx-auto h-8 w-8 text-brand-700" />
                  <h2 className="mt-3 text-base font-bold text-plum">
                    No work call-outs or inquiries yet
                  </h2>
                  <p className="mt-1 text-sm text-ink-soft">
                    Share your public storefront link ({publicStorePath}) or pin your Nigerian Ward
                    &amp; Polling Unit in Settings so nearby customers can call you for work.
                  </p>
                </CardContent>
              ) : (
                <div className="divide-y divide-line-soft">
                  {inquiriesData.results.map((inq) => {
                    const callHref = buildTelHref(inq.buyer_phone);
                    const waHref = buildWhatsAppHref(
                      inq.buyer_phone,
                      `Hello ${inq.buyer_name}, following up on your request with ${activeOrganization?.name || "our workshop"}.`
                    );
                    return (
                      <div
                        key={inq.id}
                        className="flex flex-wrap items-start justify-between gap-4 px-6 py-4"
                      >
                        <div className="space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-bold text-plum">{inq.buyer_name}</span>
                            <StatusBadge status={inq.status} />
                            <span className="rounded-full bg-surface-blush px-2.5 py-0.5 text-[10px] font-bold text-brand-700">
                              {formatStatusLabel(inq.inquiry_type)}
                            </span>
                            {inq.urgency === "emergency" && (
                              <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-[10px] font-extrabold text-red-700">
                                URGENT CALL-OUT
                              </span>
                            )}
                            {inq.urgency === "today" && (
                              <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold text-amber-800">
                                NEEDED TODAY
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-ink-soft">
                            {inq.buyer_phone}
                            {inq.buyer_email ? ` · ${inq.buyer_email}` : ""}
                            {inq.product_name
                              ? ` · Item: ${inq.product_name}${inq.quantity > 1 ? ` (x${inq.quantity})` : ""}`
                              : ""}
                            {inq.budget_amount
                              ? ` · Budget: ${formatCurrency(
                                  inq.budget_amount,
                                  activeOrganization?.currency || "NGN"
                                )}`
                              : ""}
                          </div>
                          {(inq.customer_polling_unit_name ||
                            inq.customer_ward_name ||
                            inq.customer_address) && (
                            <div className="inline-flex items-center gap-1 text-xs font-semibold text-plum">
                              <MapPin className="h-3.5 w-3.5 text-brand-600" />
                              {[
                                inq.customer_address,
                                inq.customer_polling_unit_name
                                  ? `PU: ${inq.customer_polling_unit_name}`
                                  : "",
                                inq.customer_ward_name ? `Ward: ${inq.customer_ward_name}` : "",
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                            </div>
                          )}
                          <p className="text-sm text-ink">{inq.message}</p>
                          <div className="text-[11px] text-ink-faint">
                            {formatDateTime(inq.created_at)}
                            {inq.converted_order_number && (
                              <>
                                {" "}
                                ·{" "}
                                <Link
                                  href={`/orders/${inq.converted_order}`}
                                  className="font-bold text-brand-700 hover:underline"
                                >
                                  View Order {inq.converted_order_number}
                                </Link>
                              </>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          {callHref && (
                            <a href={callHref}>
                              <Button size="sm" variant="outline">
                                <Phone className="h-3.5 w-3.5" /> Call
                              </Button>
                            </a>
                          )}
                          {waHref && (
                            <a href={waHref} target="_blank" rel="noopener noreferrer">
                              <Button size="sm" variant="outline">
                                <MessageCircle className="h-3.5 w-3.5 text-emerald-700" /> WhatsApp
                              </Button>
                            </a>
                          )}
                          {!inq.converted_order && inq.status !== "closed" && (
                            <Button
                              size="sm"
                              onClick={() => convertInquiryMutation.mutate(inq.id)}
                              disabled={convertInquiryMutation.isPending}
                            >
                              <ArrowRightCircle className="h-3.5 w-3.5" />
                              Convert to order
                            </Button>
                          )}
                          {inq.status === "new" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                updateInquiryMutation.mutate({ id: inq.id, nextStatus: "contacted" })
                              }
                            >
                              Mark contacted
                            </Button>
                          )}
                          {inq.status !== "closed" && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                updateInquiryMutation.mutate({ id: inq.id, nextStatus: "closed" })
                              }
                            >
                              Close
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
