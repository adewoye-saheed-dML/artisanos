"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Calendar as CalendarIcon,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  List,
  MapPin,
  Plus,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  Appointment,
  AppointmentType,
  Customer,
  Order,
  OrganizationMember,
  PaginatedResponse,
} from "@/types/api";

function getDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function AppointmentsContent() {
  const searchParams = useSearchParams();
  const initialCustomer = searchParams.get("customer") || "";
  const initialOrder = searchParams.get("order") || "";

  const { activeOrganization } = useAuth();
  const queryClient = useQueryClient();

  const [viewMode, setViewMode] = useState<"calendar" | "list">("calendar");
  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDayKey, setSelectedDayKey] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(!!initialCustomer);

  // Create form state
  const [customerId, setCustomerId] = useState(initialCustomer);
  const [orderId, setOrderId] = useState(initialOrder);
  const [appointmentType, setAppointmentType] = useState<AppointmentType>("first_fitting");
  const [title, setTitle] = useState("First Fitting Session");
  const [scheduledLocal, setScheduledLocal] = useState(() => {
    const d = new Date(Date.now() + 24 * 60 * 60 * 1000);
    d.setMinutes(0, 0, 0);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`;
  });
  const [durationMinutes, setDurationMinutes] = useState("30");
  const [location, setLocation] = useState("Studio Fitting Room");
  const [assignedTo, setAssignedTo] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    if (initialCustomer) {
      setCustomerId(initialCustomer);
      setShowCreate(true);
    }
    if (initialOrder) {
      setOrderId(initialOrder);
    }
  }, [initialCustomer, initialOrder]);

  const { data: appointmentsData, isLoading } = useQuery({
    queryKey: ["appointments", activeOrganization?.id],
    queryFn: () => apiRequest<PaginatedResponse<Appointment>>("/appointments/?page_size=100"),
    enabled: !!activeOrganization?.id,
  });

  const { data: customersData } = useQuery({
    queryKey: ["customers-select", activeOrganization?.id],
    queryFn: () => apiRequest<PaginatedResponse<Customer>>("/customers/?page_size=100"),
    enabled: !!activeOrganization?.id,
  });

  const { data: customerOrders } = useQuery({
    queryKey: ["customer-orders-select", activeOrganization?.id, customerId],
    queryFn: () => apiRequest<PaginatedResponse<Order>>(`/orders/?customer=${customerId}`),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const { data: members } = useQuery({
    queryKey: ["org-members", activeOrganization?.id],
    queryFn: () =>
      apiRequest<OrganizationMember[]>(`/organizations/${activeOrganization?.id}/members/`),
    enabled: !!activeOrganization?.id,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiRequest<Appointment>("/appointments/", {
        method: "POST",
        body: JSON.stringify({
          customer: customerId,
          order: orderId || null,
          appointment_type: appointmentType,
          title,
          scheduled_at: new Date(scheduledLocal).toISOString(),
          duration_minutes: Number(durationMinutes) || 30,
          location,
          assigned_to: assignedTo || null,
          notes,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      setShowCreate(false);
      setNotes("");
      setFormError("");
    },
    onError: (err) => {
      setFormError(err instanceof Error ? err.message : "Could not schedule appointment.");
    },
  });

  const actionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "complete" | "cancel" }) =>
      apiRequest<Appointment>(`/appointments/${id}/${action}/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const appointments = useMemo(() => appointmentsData?.results || [], [appointmentsData]);

  const appointmentsByDay = useMemo(() => {
    const map: Record<string, Appointment[]> = {};
    for (const appt of appointments) {
      const key = getDateKey(new Date(appt.scheduled_at));
      if (!map[key]) map[key] = [];
      map[key].push(appt);
    }
    return map;
  }, [appointments]);

  const calendarDays = useMemo(() => {
    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const firstWeekday = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells: Array<{ date: Date | null; key: string }> = [];
    for (let i = 0; i < firstWeekday; i++) {
      cells.push({ date: null, key: `empty-${i}` });
    }
    for (let day = 1; day <= daysInMonth; day++) {
      const d = new Date(year, month, day);
      cells.push({ date: d, key: getDateKey(d) });
    }
    return cells;
  }, [calendarMonth]);

  const visibleAppointments = selectedDayKey
    ? appointmentsByDay[selectedDayKey] || []
    : appointments;

  const monthLabel = calendarMonth.toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Fittings &amp; Schedule</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Appointments
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Schedule client measurement sessions, fittings, and garment collections.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-full border border-line bg-white p-1 shadow-mezer-sm">
              <button
                type="button"
                onClick={() => setViewMode("calendar")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  viewMode === "calendar"
                    ? "bg-plum text-white"
                    : "text-ink-soft hover:text-plum"
                }`}
              >
                <CalendarIcon className="h-3.5 w-3.5" /> Calendar
              </button>
              <button
                type="button"
                onClick={() => {
                  setViewMode("list");
                  setSelectedDayKey(null);
                }}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                  viewMode === "list"
                    ? "bg-plum text-white"
                    : "text-ink-soft hover:text-plum"
                }`}
              >
                <List className="h-3.5 w-3.5" /> List
              </button>
            </div>
            <Button onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {showCreate ? "Close form" : "New appointment"}
            </Button>
          </div>
        </div>

        {showCreate && (
          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">Schedule Fitting / Appointment</h2>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  createMutation.mutate();
                }}
              >
                {formError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {formError}
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="appt-customer">Customer</Label>
                    <Select
                      id="appt-customer"
                      required
                      value={customerId}
                      onChange={(e) => {
                        setCustomerId(e.target.value);
                        setOrderId("");
                      }}
                    >
                      <option value="">Select customer...</option>
                      {customersData?.results.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.full_name} ({c.phone})
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="appt-order">Linked order (optional)</Label>
                    <Select
                      id="appt-order"
                      value={orderId}
                      onChange={(e) => setOrderId(e.target.value)}
                      disabled={!customerId}
                    >
                      <option value="">None</option>
                      {customerOrders?.results.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.order_number} · {o.garment_type}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <Label htmlFor="appt-type">Type</Label>
                    <Select
                      id="appt-type"
                      value={appointmentType}
                      onChange={(e) => {
                        const val = e.target.value as AppointmentType;
                        setAppointmentType(val);
                        setTitle(formatStatusLabel(val));
                      }}
                    >
                      <option value="measurement">Measurement Session</option>
                      <option value="first_fitting">First Fitting</option>
                      <option value="final_fitting">Final Fitting</option>
                      <option value="consultation">Consultation</option>
                      <option value="collection">Order Collection</option>
                      <option value="other">Other</option>
                    </Select>
                  </div>
                  <div className="sm:col-span-2">
                    <Label htmlFor="appt-title">Title</Label>
                    <Input
                      id="appt-title"
                      required
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-4">
                  <div className="sm:col-span-2">
                    <Label htmlFor="appt-datetime">Date &amp; time</Label>
                    <Input
                      id="appt-datetime"
                      type="datetime-local"
                      required
                      value={scheduledLocal}
                      onChange={(e) => setScheduledLocal(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="appt-duration">Duration (min)</Label>
                    <Input
                      id="appt-duration"
                      type="number"
                      min={10}
                      max={480}
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="appt-assignee">Assigned artisan</Label>
                    <Select
                      id="appt-assignee"
                      value={assignedTo}
                      onChange={(e) => setAssignedTo(e.target.value)}
                    >
                      <option value="">Unassigned</option>
                      {members
                        ?.filter((m) => m.status === "active")
                        .map((m) => (
                          <option key={m.user_id} value={m.user_id}>
                            {m.full_name}
                          </option>
                        ))}
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="appt-location">Location</Label>
                    <Input
                      id="appt-location"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="appt-notes">Notes (optional)</Label>
                    <Textarea
                      id="appt-notes"
                      rows={1}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCreate(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? "Scheduling..." : "Save appointment"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {isLoading && <Card className="h-64 animate-pulse bg-white/70" />}

        {!isLoading && viewMode === "calendar" && (
          <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <h2 className="text-base font-bold text-plum">{monthLabel}</h2>
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    aria-label="Previous month"
                    onClick={() =>
                      setCalendarMonth(
                        (d) => new Date(d.getFullYear(), d.getMonth() - 1, 1)
                      )
                    }
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    aria-label="Next month"
                    onClick={() =>
                      setCalendarMonth(
                        (d) => new Date(d.getFullYear(), d.getMonth() + 1, 1)
                      )
                    }
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-bold uppercase tracking-wider text-ink-faint sm:gap-1.5 sm:text-[11px]">
                  {[
                    ["S", "Sun"],
                    ["M", "Mon"],
                    ["T", "Tue"],
                    ["W", "Wed"],
                    ["T", "Thu"],
                    ["F", "Fri"],
                    ["S", "Sat"],
                  ].map(([short, full]) => (
                    <div key={full} className="py-1">
                      <span className="sm:hidden">{short}</span>
                      <span className="hidden sm:inline">{full}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-1.5 grid grid-cols-7 gap-1 sm:gap-1.5">
                  {calendarDays.map((cell) => {
                    if (!cell.date) {
                      return (
                        <div
                          key={cell.key}
                          className="h-12 rounded-lg bg-surface/40 sm:h-20 sm:rounded-xl"
                        />
                      );
                    }
                    const dayItems = appointmentsByDay[cell.key] || [];
                    const isSelected = selectedDayKey === cell.key;
                    const isToday = getDateKey(new Date()) === cell.key;
                    return (
                      <button
                        key={cell.key}
                        type="button"
                        onClick={() =>
                          setSelectedDayKey((cur) => (cur === cell.key ? null : cell.key))
                        }
                        className={`flex h-12 flex-col items-center justify-between rounded-lg border p-1 text-center transition-all sm:h-20 sm:items-start sm:rounded-xl sm:p-2 sm:text-left ${
                          isSelected
                            ? "border-brand-700 bg-surface-blush ring-2 ring-brand-700/20"
                            : "border-line-soft bg-white hover:border-brand-300"
                        }`}
                      >
                        <span
                          className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                            isToday ? "bg-brand-700 text-white" : "text-plum"
                          }`}
                        >
                          {cell.date.getDate()}
                        </span>
                        {dayItems.length > 0 && (
                          <>
                            <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-600 px-1 text-[9px] font-extrabold text-white sm:hidden">
                              {dayItems.length}
                            </span>
                            <span className="hidden w-full truncate rounded-full bg-brand-100/80 px-2 py-0.5 text-[10px] font-bold text-brand-800 sm:inline-block">
                              {dayItems.length} {dayItems.length === 1 ? "fitting" : "fittings"}
                            </span>
                          </>
                        )}
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between">
                <h2 className="text-base font-bold text-plum">
                  {selectedDayKey ? `Schedule · ${selectedDayKey}` : "All Appointments"}
                </h2>
                {selectedDayKey && (
                  <Button size="sm" variant="ghost" onClick={() => setSelectedDayKey(null)}>
                    Show all
                  </Button>
                )}
              </CardHeader>
              <CardContent className="divide-y divide-line-soft p-0">
                {visibleAppointments.length === 0 ? (
                  <p className="p-6 text-sm text-ink-faint">
                    No appointments for this selection.
                  </p>
                ) : (
                  visibleAppointments.map((appt) => (
                    <div key={appt.id} className="space-y-2 p-5">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="text-sm font-bold text-plum">{appt.title}</div>
                          <Link
                            href={`/customers/${appt.customer}`}
                            className="text-xs font-medium text-brand-700 hover:underline"
                          >
                            {appt.customer_name}
                          </Link>
                          {appt.order && appt.order_number && (
                            <span className="text-xs text-ink-faint">
                              {" "}
                              ·{" "}
                              <Link href={`/orders/${appt.order}`} className="hover:underline">
                                {appt.order_number}
                              </Link>
                            </span>
                          )}
                        </div>
                        <StatusBadge status={appt.status} />
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs text-ink-faint">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" />
                          {formatDateTime(appt.scheduled_at)} ({appt.duration_minutes}m)
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5" />
                          {appt.location}
                        </span>
                      </div>
                      {appt.status === "scheduled" && (
                        <div className="flex gap-2 pt-1">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              actionMutation.mutate({ id: appt.id, action: "complete" })
                            }
                          >
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                            Complete
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              actionMutation.mutate({ id: appt.id, action: "cancel" })
                            }
                          >
                            Cancel
                          </Button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {!isLoading && viewMode === "list" && (
          <Card className="overflow-hidden">
            {appointments.length === 0 ? (
              <CardContent className="py-12 text-center">
                <CalendarIcon className="mx-auto h-8 w-8 text-brand-700" />
                <h2 className="mt-3 text-base font-bold text-plum">No appointments scheduled</h2>
                <p className="mt-1 text-sm text-ink-soft">
                  Schedule your first measurement session or fitting appointment.
                </p>
              </CardContent>
            ) : (
              <div className="divide-y divide-line-soft">
                {appointments.map((appt) => (
                  <div
                    key={appt.id}
                    className="flex flex-wrap items-center justify-between gap-4 px-6 py-4 hover:bg-surface-blush/50"
                  >
                    <div>
                      <div className="text-sm font-bold text-plum">
                        {appt.title}{" "}
                        <span className="font-normal text-ink-faint">
                          ({formatStatusLabel(appt.appointment_type)})
                        </span>
                      </div>
                      <div className="mt-0.5 text-xs text-ink-soft">
                        <Link
                          href={`/customers/${appt.customer}`}
                          className="font-semibold text-brand-700 hover:underline"
                        >
                          {appt.customer_name}
                        </Link>
                        {" · "}
                        {formatDateTime(appt.scheduled_at)} · {appt.duration_minutes} min ·{" "}
                        {appt.location}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={appt.status} />
                      {appt.status === "scheduled" && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              actionMutation.mutate({ id: appt.id, action: "complete" })
                            }
                          >
                            Complete
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              actionMutation.mutate({ id: appt.id, action: "cancel" })
                            }
                          >
                            Cancel
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    </AppShell>
  );
}

export default function AppointmentsPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div className="text-sm text-ink-faint">Loading appointments...</div>
        </AppShell>
      }
    >
      <AppointmentsContent />
    </Suspense>
  );
}
