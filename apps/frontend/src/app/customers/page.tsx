"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, UserPlus, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { Customer, PaginatedResponse } from "@/types/api";

const customerSchema = z.object({
  full_name: z.string().min(2, "Customer name must be at least 2 characters."),
  phone: z.string().min(5, "Valid phone number is required."),
  email: z.string().email("Enter a valid email.").optional().or(z.literal("")),
  address: z.string().optional(),
  preferred_contact_method: z.enum(["phone", "whatsapp", "email", "sms"]),
  notes: z.string().optional(),
});

type CustomerFormValues = z.infer<typeof customerSchema>;

export default function CustomersPage() {
  const { activeOrganization } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [serverError, setServerError] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["customers", activeOrganization?.id, search, showArchived],
    queryFn: () => {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (showArchived) params.set("is_archived", "true");
      return apiRequest<PaginatedResponse<Customer>>(`/customers/?${params.toString()}`);
    },
    enabled: !!activeOrganization?.id,
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CustomerFormValues>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      preferred_contact_method: "whatsapp",
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: CustomerFormValues) =>
      apiRequest<Customer>("/customers/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      reset();
      setShowCreate(false);
      setServerError("");
    },
    onError: (err) => {
      setServerError(err instanceof Error ? err.message : "Could not create customer.");
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Client Book</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Customers
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Manage customer profiles, reusable fit records, and order history.
            </p>
          </div>
          <Button className="w-full sm:w-auto" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {showCreate ? "Close form" : "Add customer"}
          </Button>
        </div>

        {showCreate && (
          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">New Customer</h2>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleSubmit((vals) => createMutation.mutate(vals))}
                className="space-y-4"
              >
                {serverError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {serverError}
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="cust-name">Full name</Label>
                    <Input id="cust-name" placeholder="Chidi Okonkwo" {...register("full_name")} />
                    {errors.full_name && (
                      <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
                    )}
                  </div>
                  <div>
                    <Label htmlFor="cust-phone">Phone number</Label>
                    <Input id="cust-phone" placeholder="+2348031234567" {...register("phone")} />
                    {errors.phone && (
                      <p className="mt-1 text-xs text-red-600">{errors.phone.message}</p>
                    )}
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="cust-email">Email (optional)</Label>
                    <Input id="cust-email" type="email" placeholder="chidi@example.com" {...register("email")} />
                    {errors.email && (
                      <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                    )}
                  </div>
                  <div>
                    <Label htmlFor="cust-contact">Preferred contact method</Label>
                    <Select id="cust-contact" {...register("preferred_contact_method")}>
                      <option value="whatsapp">WhatsApp</option>
                      <option value="phone">Phone call</option>
                      <option value="sms">SMS</option>
                      <option value="email">Email</option>
                    </Select>
                  </div>
                </div>

                <div>
                  <Label htmlFor="cust-address">Address (optional)</Label>
                  <Input id="cust-address" placeholder="Victoria Island, Lagos" {...register("address")} />
                </div>

                <div>
                  <Label htmlFor="cust-notes">Notes (optional)</Label>
                  <Textarea id="cust-notes" rows={2} placeholder="Fit preferences, posture notes..." {...register("notes")} />
                </div>

                <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={() => setShowCreate(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="w-full sm:w-auto"
                    disabled={createMutation.isPending}
                  >
                    {createMutation.isPending ? "Saving..." : "Save customer"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-3.5 h-4 w-4 text-ink-faint" />
            <Input
              aria-label="Search customers"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by customer name, phone, or email..."
              className="mt-0 rounded-full bg-white pl-10 shadow-mezer-sm"
            />
          </div>
          <Button
            variant={showArchived ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowArchived((v) => !v)}
          >
            {showArchived ? "Viewing archived" : "Show archived"}
          </Button>
        </div>

        {isLoading && <Card className="h-40 animate-pulse bg-white/70" />}

        {error && (
          <div className="rounded-mezer-sm border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Could not load customers: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {data && (
          <Card className="overflow-hidden">
            {data.results.length === 0 ? (
              <CardContent className="py-12 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                  <UserPlus className="h-6 w-6" />
                </div>
                <h2 className="mt-3 text-base font-bold text-plum">
                  {search ? "No matching customers" : "No customers yet"}
                </h2>
                <p className="mt-1 text-sm text-ink-soft">
                  {search
                    ? "Try a different name or phone number."
                    : "Add your first customer to start recording measurements and orders."}
                </p>
              </CardContent>
            ) : (
              <>
                {/* Mobile Card List */}
                <div className="divide-y divide-line-soft sm:hidden">
                  {data.results.map((c) => (
                    <div key={c.id} className="space-y-2.5 p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <Link
                            href={`/customers/${c.id}`}
                            className="block truncate text-sm font-bold text-plum hover:text-brand-700"
                          >
                            {c.full_name}
                          </Link>
                          <div className="text-xs text-ink-soft">{c.phone}</div>
                          {c.email && (
                            <div className="truncate text-xs text-ink-faint">{c.email}</div>
                          )}
                        </div>
                        <span className="shrink-0 rounded-full bg-surface-blush px-2.5 py-0.5 text-[10px] font-bold capitalize text-brand-700">
                          {c.preferred_contact_method}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-2 pt-1">
                        <span className="text-[11px] text-ink-faint">
                          {formatDateTime(c.created_at)}
                        </span>
                        <Link href={`/customers/${c.id}`}>
                          <Button variant="outline" size="sm">
                            Open profile
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
                        <th className="px-6 py-3.5">Customer</th>
                        <th className="px-6 py-3.5">Phone</th>
                        <th className="hidden px-6 py-3.5 sm:table-cell">Preferred Contact</th>
                        <th className="hidden px-6 py-3.5 md:table-cell">Created</th>
                        <th className="px-6 py-3.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line-soft">
                      {data.results.map((c) => (
                        <tr key={c.id} className="transition-colors hover:bg-surface-blush/60">
                          <td className="px-6 py-4">
                            <Link
                              href={`/customers/${c.id}`}
                              className="font-semibold text-plum hover:text-brand-700 hover:underline"
                            >
                              {c.full_name}
                            </Link>
                            {c.email && <div className="text-xs text-ink-faint">{c.email}</div>}
                          </td>
                          <td className="px-6 py-4 text-ink-soft">{c.phone}</td>
                          <td className="hidden px-6 py-4 capitalize text-ink-soft sm:table-cell">
                            {c.preferred_contact_method}
                          </td>
                          <td className="hidden px-6 py-4 text-xs text-ink-faint md:table-cell">
                            {formatDateTime(c.created_at)}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <Link href={`/customers/${c.id}`}>
                              <Button variant="outline" size="sm">
                                Open profile
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
