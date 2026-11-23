"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  Customer,
  MeasurementProfile,
  Order,
  OrderDetail,
  OrderStatus,
  PaginatedResponse,
} from "@/types/api";

const ORDER_STATUSES: OrderStatus[] = [
  "draft",
  "awaiting_measurements",
  "quoted",
  "confirmed",
  "in_production",
  "fitting",
  "ready",
  "completed",
  "on_hold",
  "cancelled",
];

const CATEGORY_OPTION_FIELDS: Record<
  string,
  Array<{ key: string; label: string; placeholder: string }>
> = {
  tailor: [
    { key: "fabric_source", label: "Fabric source", placeholder: "Client supplied / Studio wool" },
    { key: "collar_or_lapel", label: "Collar / lapel style", placeholder: "Peak lapel / Mandarin collar" },
    { key: "lining", label: "Lining preference", placeholder: "Half-lined silk / Unlined" },
  ],
  shoemaker: [
    { key: "sole_type", label: "Sole construction", placeholder: "Goodyear welted / Blake stitched" },
    { key: "toe_shape", label: "Toe / last shape", placeholder: "Almond / Chisel / Round" },
    { key: "leather_grade", label: "Leather grade", placeholder: "Full-grain calfskin / Suede" },
  ],
  leatherworker: [
    { key: "leather_hide", label: "Leather hide", placeholder: "Vegetable-tanned bridle / Pebbled" },
    { key: "hardware_finish", label: "Hardware finish", placeholder: "Solid brass / Brushed nickel" },
    { key: "monogram", label: "Monogram / stitching", placeholder: "Blind deboss 'A.O' / Cream linen" },
  ],
  electrician: [
    { key: "fault_or_scope", label: "Electrical scope / fault", placeholder: "Inverter install / Breaker tripping" },
    { key: "load_capacity", label: "Load / voltage rating", placeholder: "3.5kVA / Single-phase 220V" },
    { key: "site_landmark", label: "Site ward / landmark", placeholder: "Allen Roundabout, Ikeja" },
  ],
  plumber: [
    { key: "issue_type", label: "Plumbing issue / install", placeholder: "Burst pipe / Shower mixer / Borehole" },
    { key: "pipe_spec", label: "Pipe / fitting spec", placeholder: "PPR 25mm / Concealed brass" },
    { key: "site_landmark", label: "Site ward / landmark", placeholder: "Bode Thomas, Surulere" },
  ],
  carpenter: [
    { key: "wood_material", label: "Wood / board material", placeholder: "Marine board / HDF / Mahogany" },
    { key: "dimensions", label: "Dimensions", placeholder: "6ft x 2ft x 1.5ft" },
    { key: "finish", label: "Finish & color", placeholder: "Matte walnut / Gloss white" },
  ],
  mechanic: [
    { key: "vehicle_model", label: "Vehicle make & year", placeholder: "Toyota Camry 2015" },
    { key: "fault_symptoms", label: "Fault / service needed", placeholder: "OBD scan / Brake pads / Oil service" },
    { key: "parts_source", label: "Parts supplied by", placeholder: "Artisan / Customer supplied" },
  ],
  other: [
    { key: "material", label: "Primary material / scope", placeholder: "Material or service specification" },
    { key: "site_or_finish", label: "Finish / site notes", placeholder: "Custom finish or site landmark" },
  ],
};

function OrdersContent() {
  const searchParams = useSearchParams();
  const initialCustomer = searchParams.get("customer") || "";

  const { activeOrganization } = useAuth();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreate, setShowCreate] = useState(!!initialCustomer);

  const [customerId, setCustomerId] = useState(initialCustomer);
  const [measurementProfileId, setMeasurementProfileId] = useState("");
  const [garmentType, setGarmentType] = useState("");
  const [description, setDescription] = useState("");
  const [quotedAmount, setQuotedAmount] = useState("0.00");
  const [depositAmount, setDepositAmount] = useState("0.00");
  const [initialStatus, setInitialStatus] = useState<"draft" | "awaiting_measurements" | "quoted" | "confirmed">("quoted");
  const [deliveryMethod, setDeliveryMethod] = useState<"pickup" | "delivery" | "shipping">("pickup");
  const [expectedDate, setExpectedDate] = useState("");
  const [instructions, setInstructions] = useState("");
  const [categoryOptions, setCategoryOptions] = useState<Record<string, string>>({});
  const [createError, setCreateError] = useState("");

  const activeCategoryFields =
    CATEGORY_OPTION_FIELDS[activeOrganization?.category || "tailor"] ||
    CATEGORY_OPTION_FIELDS.other;

  useEffect(() => {
    if (initialCustomer) {
      setCustomerId(initialCustomer);
      setShowCreate(true);
    }
  }, [initialCustomer]);

  const { data: ordersData, isLoading } = useQuery({
    queryKey: ["orders", activeOrganization?.id, search, statusFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (statusFilter) params.set("status", statusFilter);
      return apiRequest<PaginatedResponse<Order>>(`/orders/?${params.toString()}`);
    },
    enabled: !!activeOrganization?.id,
  });

  const { data: customersData } = useQuery({
    queryKey: ["customers-select", activeOrganization?.id],
    queryFn: () => apiRequest<PaginatedResponse<Customer>>("/customers/?page_size=100"),
    enabled: !!activeOrganization?.id,
  });

  const { data: customerProfiles } = useQuery({
    queryKey: ["customer-measurements", activeOrganization?.id, customerId],
    queryFn: () =>
      apiRequest<PaginatedResponse<MeasurementProfile>>(`/customers/${customerId}/measurements/`),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  useEffect(() => {
    const latest = customerProfiles?.results.find((p) => p.is_latest) || customerProfiles?.results[0];
    if (latest) {
      setMeasurementProfileId(latest.id);
    } else {
      setMeasurementProfileId("");
    }
  }, [customerProfiles]);

  const createMutation = useMutation({
    mutationFn: () =>
      apiRequest<OrderDetail>("/orders/", {
        method: "POST",
        body: JSON.stringify({
          customer: customerId,
          garment_type: garmentType,
          description,
          measurement_profile: measurementProfileId || null,
          status: initialStatus,
          quoted_amount: quotedAmount || "0.00",
          deposit_amount: depositAmount || "0.00",
          delivery_method: deliveryMethod,
          expected_completion_date: expectedDate || null,
          category_options: Object.fromEntries(
            Object.entries(categoryOptions).filter(([, v]) => v.trim().length > 0)
          ),
          customer_instructions: instructions,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      setGarmentType("");
      setDescription("");
      setQuotedAmount("0.00");
      setDepositAmount("0.00");
      setInstructions("");
      setCategoryOptions({});
      setShowCreate(false);
      setCreateError("");
    },
    onError: (err) => {
      setCreateError(err instanceof Error ? err.message : "Could not create order.");
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Order Pipeline</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Tailoring Orders
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Track customer orders, quotes, frozen measurement snapshots, and production milestones.
            </p>
          </div>
          <Button onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {showCreate ? "Close form" : "New order"}
          </Button>
        </div>

        {showCreate && (
          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">Create Tailoring Order</h2>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  createMutation.mutate();
                }}
              >
                {createError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {createError}
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="ord-customer">Customer</Label>
                    <Select
                      id="ord-customer"
                      required
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                    >
                      <option value="">Select a customer...</option>
                      {customersData?.results.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.full_name} ({c.phone})
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="ord-profile">Measurement profile</Label>
                    <Select
                      id="ord-profile"
                      value={measurementProfileId}
                      onChange={(e) => setMeasurementProfileId(e.target.value)}
                      disabled={!customerId}
                    >
                      <option value="">None attached yet</option>
                      {customerProfiles?.results.map((p) => (
                        <option key={p.id} value={p.id}>
                          v{p.version_number} · {p.label} ({p.unit_system}, {p.status})
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="ord-garment">Garment / item type</Label>
                    <Input
                      id="ord-garment"
                      required
                      placeholder="e.g. 3-Piece Navy Wool Suit / Agbada"
                      value={garmentType}
                      onChange={(e) => setGarmentType(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="ord-status">Initial status</Label>
                    <Select
                      id="ord-status"
                      value={initialStatus}
                      onChange={(e) =>
                        setInitialStatus(
                          e.target.value as "draft" | "awaiting_measurements" | "quoted" | "confirmed"
                        )
                      }
                    >
                      <option value="draft">Draft</option>
                      <option value="awaiting_measurements">Awaiting Measurements</option>
                      <option value="quoted">Quoted</option>
                      <option value="confirmed">Confirmed</option>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-4">
                  <div>
                    <Label htmlFor="ord-quote">
                      Quoted amount ({activeOrganization?.currency})
                    </Label>
                    <Input
                      id="ord-quote"
                      type="number"
                      step="0.01"
                      min="0"
                      value={quotedAmount}
                      onChange={(e) => setQuotedAmount(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="ord-deposit">
                      Deposit paid ({activeOrganization?.currency})
                    </Label>
                    <Input
                      id="ord-deposit"
                      type="number"
                      step="0.01"
                      min="0"
                      value={depositAmount}
                      onChange={(e) => setDepositAmount(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="ord-delivery">Delivery method</Label>
                    <Select
                      id="ord-delivery"
                      value={deliveryMethod}
                      onChange={(e) =>
                        setDeliveryMethod(e.target.value as "pickup" | "delivery" | "shipping")
                      }
                    >
                      <option value="pickup">Studio Pickup</option>
                      <option value="delivery">Local Delivery</option>
                      <option value="shipping">Courier / Shipping</option>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="ord-due">Target completion date</Label>
                    <Input
                      id="ord-due"
                      type="date"
                      value={expectedDate}
                      onChange={(e) => setExpectedDate(e.target.value)}
                    />
                  </div>
                </div>

                <div className="rounded-mezer-sm border border-line bg-surface-blush p-4">
                  <div className="mb-3 text-xs font-extrabold uppercase tracking-wider text-brand-700">
                    {activeOrganization?.category || "Tailor"} Specifications (optional)
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    {activeCategoryFields.map((spec) => (
                      <div key={spec.key}>
                        <Label htmlFor={`cat-opt-${spec.key}`}>{spec.label}</Label>
                        <Input
                          id={`cat-opt-${spec.key}`}
                          className="bg-white"
                          placeholder={spec.placeholder}
                          value={categoryOptions[spec.key] || ""}
                          onChange={(e) =>
                            setCategoryOptions((prev) => ({
                              ...prev,
                              [spec.key]: e.target.value,
                            }))
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <Label htmlFor="ord-instructions">Style &amp; customer instructions</Label>
                  <Textarea
                    id="ord-instructions"
                    rows={2}
                    placeholder="Fabric details, lapel style, embroidery notes..."
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCreate(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? "Creating order..." : "Create order"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-ink-faint" />
            <Input
              aria-label="Search orders"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search order number, garment type, or customer..."
              className="mt-0 rounded-full bg-white pl-10 shadow-mezer-sm"
            />
          </div>
          <Select
            aria-label="Filter by status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="mt-0 rounded-full bg-white shadow-mezer-sm sm:w-56"
          >
            <option value="">All statuses</option>
            {ORDER_STATUSES.map((s) => (
              <option key={s} value={s}>
                {formatStatusLabel(s)}
              </option>
            ))}
          </Select>
        </div>

        {isLoading && <Card className="h-44 animate-pulse bg-white/70" />}

        {ordersData && (
          <Card className="overflow-hidden">
            {ordersData.results.length === 0 ? (
              <CardContent className="py-12 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                  <ClipboardList className="h-6 w-6" />
                </div>
                <h2 className="mt-3 text-base font-bold text-plum">No orders found</h2>
                <p className="mt-1 text-sm text-ink-soft">
                  Create a tailoring order and link a customer measurement profile to begin.
                </p>
              </CardContent>
            ) : (
              <>
                {/* Mobile Card List */}
                <div className="divide-y divide-line-soft sm:hidden">
                  {ordersData.results.map((order) => (
                    <div key={order.id} className="space-y-2.5 p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <Link
                            href={`/orders/${order.id}`}
                            className="block truncate text-sm font-bold text-plum hover:text-brand-700"
                          >
                            {order.order_number} · {order.garment_type}
                          </Link>
                          <Link
                            href={`/customers/${order.customer}`}
                            className="text-xs text-ink-soft hover:text-brand-700"
                          >
                            {order.customer_name}
                          </Link>
                        </div>
                        <StatusBadge status={order.status} />
                      </div>
                      <div className="flex items-center justify-between gap-2 pt-1">
                        <div>
                          <div className="text-xs font-bold text-plum">
                            {formatCurrency(order.quoted_amount, order.currency)}
                          </div>
                          <div className="text-[11px] text-ink-faint">
                            Deposit: {formatCurrency(order.deposit_amount, order.currency)}
                          </div>
                        </div>
                        <Link href={`/orders/${order.id}`}>
                          <Button size="sm" variant="outline">
                            Manage
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Desktop Table */}
                <div className="hidden overflow-x-auto sm:block">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-line bg-surface-blush text-[11px] font-bold uppercase tracking-wider text-ink-faint">
                      <tr>
                        <th className="px-6 py-3.5">Order</th>
                        <th className="px-6 py-3.5">Customer</th>
                        <th className="px-6 py-3.5">Status</th>
                        <th className="hidden px-6 py-3.5 sm:table-cell">Quote / Deposit</th>
                        <th className="hidden px-6 py-3.5 md:table-cell">Created</th>
                        <th className="px-6 py-3.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line-soft">
                      {ordersData.results.map((order) => (
                        <tr key={order.id} className="transition-colors hover:bg-surface-blush/60">
                          <td className="px-6 py-4">
                            <Link
                              href={`/orders/${order.id}`}
                              className="font-semibold text-plum hover:text-brand-700 hover:underline"
                            >
                              {order.order_number}
                            </Link>
                            <div className="text-xs text-ink-soft">{order.garment_type}</div>
                          </td>
                          <td className="px-6 py-4">
                            <Link
                              href={`/customers/${order.customer}`}
                              className="text-ink-soft hover:text-brand-700 hover:underline"
                            >
                              {order.customer_name}
                            </Link>
                          </td>
                          <td className="px-6 py-4">
                            <StatusBadge status={order.status} />
                          </td>
                          <td className="hidden px-6 py-4 sm:table-cell">
                            <div className="font-semibold text-plum">
                              {formatCurrency(order.quoted_amount, order.currency)}
                            </div>
                            <div className="text-xs text-ink-faint">
                              Deposit: {formatCurrency(order.deposit_amount, order.currency)}
                            </div>
                          </td>
                          <td className="hidden px-6 py-4 text-xs text-ink-faint md:table-cell">
                            {formatDateTime(order.created_at)}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <Link href={`/orders/${order.id}`}>
                              <Button size="sm" variant="outline">
                                Manage
                              </Button>
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Card>
        )}
      </div>
    </AppShell>
  );
}

export default function OrdersPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div className="text-sm text-ink-faint">Loading orders...</div>
        </AppShell>
      }
    >
      <OrdersContent />
    </Suspense>
  );
}
