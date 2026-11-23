"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Check,
  CheckSquare,
  Clock,
  ListChecks,
  Plus,
  Ruler,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  Appointment,
  OrderDetail,
  OrderStatus,
  OrganizationMember,
  PaginatedResponse,
  ProductionTask,
  ProductionTaskStage,
  ProductionTaskStatus,
} from "@/types/api";

export default function OrderDetailPage() {
  const params = useParams<{ id: string }>();
  const orderId = params.id;
  const { activeOrganization } = useAuth();
  const queryClient = useQueryClient();

  const [transitionNote, setTransitionNote] = useState("");
  const [transitionError, setTransitionError] = useState("");

  // Production task form state
  const [showAddTask, setShowAddTask] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskStage, setTaskStage] = useState<ProductionTaskStage>("sewing");
  const [taskAlteration, setTaskAlteration] = useState(false);
  const [taskAssignee, setTaskAssignee] = useState("");
  const [taskDue, setTaskDue] = useState("");
  const [taskError, setTaskError] = useState("");

  const { data: order, isLoading, error } = useQuery({
    queryKey: ["order", activeOrganization?.id, orderId],
    queryFn: () => apiRequest<OrderDetail>(`/orders/${orderId}/`),
    enabled: !!activeOrganization?.id && !!orderId,
  });

  const { data: tasksData } = useQuery({
    queryKey: ["order-tasks", activeOrganization?.id, orderId],
    queryFn: () =>
      apiRequest<PaginatedResponse<ProductionTask>>(`/production/tasks/?order=${orderId}`),
    enabled: !!activeOrganization?.id && !!orderId,
  });

  const { data: appointmentsData } = useQuery({
    queryKey: ["order-appointments", activeOrganization?.id, orderId],
    queryFn: () =>
      apiRequest<PaginatedResponse<Appointment>>(`/appointments/?order=${orderId}`),
    enabled: !!activeOrganization?.id && !!orderId,
  });

  const { data: members } = useQuery({
    queryKey: ["org-members", activeOrganization?.id],
    queryFn: () =>
      apiRequest<OrganizationMember[]>(`/organizations/${activeOrganization?.id}/members/`),
    enabled: !!activeOrganization?.id,
  });

  const transitionMutation = useMutation({
    mutationFn: (toStatus: OrderStatus) =>
      apiRequest<OrderDetail>(`/orders/${orderId}/transition/`, {
        method: "POST",
        body: JSON.stringify({
          to_status: toStatus,
          notes: transitionNote,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order", activeOrganization?.id, orderId] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["production-board"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      setTransitionNote("");
      setTransitionError("");
    },
    onError: (err) => {
      setTransitionError(err instanceof Error ? err.message : "Could not update order status.");
    },
  });

  const seedChecklistMutation = useMutation({
    mutationFn: () =>
      apiRequest<ProductionTask[]>(`/production/orders/${orderId}/seed-checklist/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order-tasks", activeOrganization?.id, orderId] });
      queryClient.invalidateQueries({ queryKey: ["production-board"] });
    },
  });

  const createTaskMutation = useMutation({
    mutationFn: () =>
      apiRequest<ProductionTask>("/production/tasks/", {
        method: "POST",
        body: JSON.stringify({
          order: orderId,
          title: taskTitle,
          stage: taskAlteration ? "alteration" : taskStage,
          is_alteration: taskAlteration,
          assigned_to: taskAssignee || null,
          due_date: taskDue || null,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order-tasks", activeOrganization?.id, orderId] });
      queryClient.invalidateQueries({ queryKey: ["production-board"] });
      setTaskTitle("");
      setTaskAlteration(false);
      setTaskDue("");
      setShowAddTask(false);
      setTaskError("");
    },
    onError: (err) => {
      setTaskError(err instanceof Error ? err.message : "Could not add production task.");
    },
  });

  const updateTaskStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProductionTaskStatus }) =>
      apiRequest<ProductionTask>(`/production/tasks/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order-tasks", activeOrganization?.id, orderId] });
      queryClient.invalidateQueries({ queryKey: ["production-board"] });
    },
  });

  const deleteTaskMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/production/tasks/${id}/`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["order-tasks", activeOrganization?.id, orderId] });
      queryClient.invalidateQueries({ queryKey: ["production-board"] });
    },
  });

  const tasks = tasksData?.results || [];
  const doneCount = tasks.filter((t) => t.status === "done").length;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:gap-3">
            <Link href="/orders" className="self-start sm:mt-1">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4" />
                Orders
              </Button>
            </Link>
            <div className="min-w-0">
              <div className="mezer-eyebrow">Order Record</div>
              <h1 className="mt-1 break-words text-xl font-extrabold tracking-tight text-plum sm:text-3xl">
                {order ? `${order.order_number} · ${order.garment_type}` : "Order Detail"}
              </h1>
              {order && (
                <p className="mt-0.5 text-sm text-ink-soft">
                  Customer:{" "}
                  <Link
                    href={`/customers/${order.customer}`}
                    className="font-semibold text-brand-700 hover:underline"
                  >
                    {order.customer_name}
                  </Link>
                </p>
              )}
            </div>
          </div>
          {order && (
            <div className="flex flex-wrap items-center gap-2">
              <Link href={`/appointments?customer=${order.customer}&order=${order.id}`}>
                <Button variant="outline" size="sm">
                  <Calendar className="h-4 w-4" />
                  Schedule fitting
                </Button>
              </Link>
              <StatusBadge status={order.status} className="px-3.5 py-1 text-sm" />
            </div>
          )}
        </div>

        {isLoading && <Card className="h-48 animate-pulse bg-white/70" />}

        {error && (
          <div className="rounded-mezer-sm border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Could not load order: {error instanceof Error ? error.message : "Unknown error"}
          </div>
        )}

        {order && (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              {/* Status Transition Controls */}
              <Card>
                <CardHeader>
                  <h2 className="text-base font-bold text-plum">Update Order Status</h2>
                </CardHeader>
                <CardContent className="space-y-4">
                  {transitionError && (
                    <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                      {transitionError}
                    </div>
                  )}

                  {order.allowed_next_statuses.length === 0 ? (
                    <p className="text-sm text-ink-soft">
                      This order is in a terminal state ({formatStatusLabel(order.status)}).
                    </p>
                  ) : (
                    <>
                      <div>
                        <Label htmlFor="transition-note">Transition note (optional)</Label>
                        <Input
                          id="transition-note"
                          value={transitionNote}
                          onChange={(e) => setTransitionNote(e.target.value)}
                          placeholder="e.g. Fabric cut, first fitting scheduled..."
                        />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {order.allowed_next_statuses.map((nextStatus) => (
                          <Button
                            key={nextStatus}
                            size="sm"
                            variant={nextStatus === "cancelled" ? "danger" : "primary"}
                            disabled={transitionMutation.isPending}
                            onClick={() => transitionMutation.mutate(nextStatus)}
                          >
                            <Check className="h-3.5 w-3.5" />
                            Move to {formatStatusLabel(nextStatus)}
                          </Button>
                        ))}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* Production Task Checklist */}
              <Card>
                <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                      <ListChecks className="h-4 w-4" />
                    </div>
                    <div>
                      <h2 className="text-base font-bold text-plum">Production Checklist</h2>
                      <p className="text-xs text-ink-faint">
                        {tasks.length === 0
                          ? "No tasks added yet"
                          : `${doneCount} of ${tasks.length} tasks completed`}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {tasks.length === 0 && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={seedChecklistMutation.isPending}
                        onClick={() => seedChecklistMutation.mutate()}
                      >
                        <CheckSquare className="h-3.5 w-3.5" />
                        Add tailoring checklist
                      </Button>
                    )}
                    <Button size="sm" onClick={() => setShowAddTask((v) => !v)}>
                      <Plus className="h-3.5 w-3.5" />
                      Add task
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {showAddTask && (
                    <form
                      className="space-y-3 rounded-mezer-sm border border-line bg-surface-blush p-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        createTaskMutation.mutate();
                      }}
                    >
                      {taskError && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                          {taskError}
                        </div>
                      )}
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <Label htmlFor="task-title">Task title</Label>
                          <Input
                            id="task-title"
                            required
                            className="bg-white"
                            placeholder="e.g. Taper sleeves or hand-stitch lapel"
                            value={taskTitle}
                            onChange={(e) => setTaskTitle(e.target.value)}
                          />
                        </div>
                        <div>
                          <Label htmlFor="task-stage">Stage</Label>
                          <Select
                            id="task-stage"
                            className="bg-white"
                            value={taskStage}
                            onChange={(e) => setTaskStage(e.target.value as ProductionTaskStage)}
                          >
                            <option value="cutting">Cutting</option>
                            <option value="sewing">Sewing &amp; Assembly</option>
                            <option value="embroidery">Embroidery / Detailing</option>
                            <option value="fitting">Fitting Adjustment</option>
                            <option value="alteration">Alteration</option>
                            <option value="finishing">Finishing &amp; Pressing</option>
                            <option value="quality_check">Quality Check</option>
                            <option value="other">Other</option>
                          </Select>
                        </div>
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div>
                          <Label htmlFor="task-assignee">Assign artisan (optional)</Label>
                          <Select
                            id="task-assignee"
                            className="bg-white"
                            value={taskAssignee}
                            onChange={(e) => setTaskAssignee(e.target.value)}
                          >
                            <option value="">Unassigned</option>
                            {members
                              ?.filter((m) => m.status === "active")
                              .map((m) => (
                                <option key={m.user_id} value={m.user_id}>
                                  {m.full_name} ({m.role})
                                </option>
                              ))}
                          </Select>
                        </div>
                        <div>
                          <Label htmlFor="task-due">Due date (optional)</Label>
                          <Input
                            id="task-due"
                            type="date"
                            className="bg-white"
                            value={taskDue}
                            onChange={(e) => setTaskDue(e.target.value)}
                          />
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                        <label className="flex items-center gap-2 text-xs font-semibold text-ink">
                          <input
                            type="checkbox"
                            className="accent-brand-700"
                            checked={taskAlteration}
                            onChange={(e) => setTaskAlteration(e.target.checked)}
                          />
                          Flag as alteration request
                        </label>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => setShowAddTask(false)}>
                            Cancel
                          </Button>
                          <Button size="sm" type="submit" disabled={createTaskMutation.isPending}>
                            {createTaskMutation.isPending ? "Adding..." : "Save task"}
                          </Button>
                        </div>
                      </div>
                    </form>
                  )}

                  {tasks.length === 0 ? (
                    <p className="text-sm text-ink-faint">
                      Use &ldquo;Add tailoring checklist&rdquo; for the standard 5-step workflow or add custom tasks.
                    </p>
                  ) : (
                    <div className="divide-y divide-line-soft rounded-mezer-sm border border-line">
                      {tasks.map((task) => (
                        <div
                          key={task.id}
                          className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                        >
                          <div className="flex items-start gap-3">
                            <input
                              type="checkbox"
                              aria-label={`Mark ${task.title} complete`}
                              className="mt-1 h-4 w-4 accent-brand-700"
                              checked={task.status === "done"}
                              onChange={(e) =>
                                updateTaskStatusMutation.mutate({
                                  id: task.id,
                                  status: e.target.checked ? "done" : "todo",
                                })
                              }
                            />
                            <div>
                              <div
                                className={`text-sm font-semibold ${
                                  task.status === "done"
                                    ? "line-through text-ink-faint"
                                    : "text-plum"
                                }`}
                              >
                                {task.title}
                              </div>
                              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
                                <span className="capitalize">{formatStatusLabel(task.stage)}</span>
                                {task.is_alteration && (
                                  <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                                    <AlertTriangle className="h-3 w-3" /> Alteration
                                  </span>
                                )}
                                {task.assigned_to_name && <span>· {task.assigned_to_name}</span>}
                                {task.due_date && <span>· Due {task.due_date}</span>}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Select
                              aria-label={`Status for ${task.title}`}
                              value={task.status}
                              className="mt-0 w-32 py-1 text-xs"
                              onChange={(e) =>
                                updateTaskStatusMutation.mutate({
                                  id: task.id,
                                  status: e.target.value as ProductionTaskStatus,
                                })
                              }
                            >
                              <option value="todo">To Do</option>
                              <option value="in_progress">In Progress</option>
                              <option value="blocked">Blocked</option>
                              <option value="done">Done</option>
                            </Select>
                            <button
                              type="button"
                              aria-label={`Delete ${task.title}`}
                              onClick={() => deleteTaskMutation.mutate(task.id)}
                              className="rounded-full p-1.5 text-ink-faint hover:bg-red-50 hover:text-red-600"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Order Summary */}
              <Card>
                <CardHeader>
                  <h2 className="text-base font-bold text-plum">Order Details</h2>
                </CardHeader>
                <CardContent className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <div className="text-xs font-medium text-ink-faint">Quoted Amount</div>
                    <div className="mt-0.5 text-base font-bold text-plum">
                      {formatCurrency(order.quoted_amount, order.currency)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-ink-faint">Deposit Paid</div>
                    <div className="mt-0.5 text-base font-bold text-plum">
                      {formatCurrency(order.deposit_amount, order.currency)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-ink-faint">Payment Status</div>
                    <div className="mt-1">
                      <StatusBadge status={order.payment_status} />
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-ink-faint">Delivery Method</div>
                    <div className="mt-0.5 text-sm font-semibold capitalize text-ink">
                      {order.delivery_method}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-ink-faint">Expected Completion</div>
                    <div className="mt-0.5 text-sm font-semibold text-ink">
                      {order.expected_completion_date || "Not set"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-ink-faint">Created</div>
                    <div className="mt-0.5 text-sm text-ink-soft">{formatDateTime(order.created_at)}</div>
                  </div>
                  {order.category_options && Object.keys(order.category_options).length > 0 && (
                    <div className="grid gap-2.5 sm:col-span-3 sm:grid-cols-3">
                      {Object.entries(order.category_options).map(([k, v]) => (
                        <div
                          key={k}
                          className="rounded-mezer-sm border border-line-soft bg-surface p-3"
                        >
                          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                            {formatStatusLabel(k)}
                          </div>
                          <div className="mt-0.5 text-sm font-bold text-plum">{v}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {order.customer_instructions && (
                    <div className="rounded-mezer-sm border border-line-soft bg-surface-blush p-3.5 text-sm text-ink sm:col-span-3">
                      <span className="font-bold text-plum">Customer instructions:</span>{" "}
                      {order.customer_instructions}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Frozen Measurement Snapshot */}
              <Card>
                <CardHeader className="flex flex-row items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                    <Ruler className="h-4 w-4" />
                  </div>
                  <h2 className="text-base font-bold text-plum">Frozen Measurement Snapshot</h2>
                </CardHeader>
                <CardContent>
                  {!order.measurement_snapshot ? (
                    <p className="text-sm text-ink-faint">
                      No measurement profile linked to this order yet.
                    </p>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap gap-2.5 text-xs text-ink-soft">
                        <span className="rounded-full bg-surface-blush px-3 py-1 font-semibold text-brand-700">
                          {order.measurement_snapshot.label} · v{order.measurement_snapshot.version_number}
                        </span>
                        <span className="rounded-full bg-surface px-3 py-1">
                          {order.measurement_snapshot.template_name}
                        </span>
                        <span className="rounded-full bg-surface px-3 py-1 uppercase">
                          {order.measurement_snapshot.unit_system}
                        </span>
                        <span className="rounded-full bg-surface px-3 py-1">
                          Captured {formatDateTime(order.measurement_snapshot.captured_at)}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                        {order.measurement_snapshot.values.map((v) => (
                          <div
                            key={v.field_key}
                            className="rounded-mezer-sm border border-line-soft bg-surface-blush p-3"
                          >
                            <div className="text-xs text-ink-soft">{v.field_label}</div>
                            <div className="mt-0.5 text-base font-extrabold text-plum">
                              {v.text_value || `${v.numeric_value} ${v.unit}`}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Sidebar: Activity Timeline & Linked Fittings */}
            <div className="space-y-6">
              <Card>
                <CardHeader className="flex flex-row items-center gap-2">
                  <Clock className="h-4 w-4 text-brand-700" />
                  <h2 className="text-base font-bold text-plum">Activity Timeline</h2>
                </CardHeader>
                <CardContent className="space-y-5">
                  {order.status_events.map((ev) => (
                    <div key={ev.id} className="relative border-l-2 border-brand-200 pl-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={ev.to_status} />
                        <span className="text-xs text-ink-faint">
                          {formatDateTime(ev.created_at)}
                        </span>
                      </div>
                      {ev.from_status && (
                        <div className="mt-1 text-xs text-ink-faint">
                          From {formatStatusLabel(ev.from_status)}
                        </div>
                      )}
                      {ev.notes && <p className="mt-1 text-sm text-ink">{ev.notes}</p>}
                      {ev.changed_by_name && (
                        <p className="mt-0.5 text-[11px] font-medium text-ink-faint">
                          By {ev.changed_by_name}
                        </p>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card className="overflow-hidden">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-brand-700" />
                    <h2 className="text-base font-bold text-plum">Linked Fittings</h2>
                  </div>
                </CardHeader>
                <CardContent className="divide-y divide-line-soft p-0">
                  {!appointmentsData?.results.length ? (
                    <p className="p-5 text-sm text-ink-faint">No fittings scheduled for this order.</p>
                  ) : (
                    appointmentsData.results.map((appt) => (
                      <div key={appt.id} className="px-5 py-3.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-plum">{appt.title}</span>
                          <StatusBadge status={appt.status} />
                        </div>
                        <div className="mt-1 text-xs text-ink-faint">
                          {formatDateTime(appt.scheduled_at)} · {appt.location}
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
