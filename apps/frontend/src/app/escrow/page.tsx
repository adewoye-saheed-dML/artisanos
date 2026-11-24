"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCopy,
  KeyRound,
  Lock,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { EscrowFundResponse, EscrowTransaction } from "@/types/api";

function EscrowContent() {
  const { user, activeOrganization } = useAuth();
  const queryClient = useQueryClient();

  const [roleView, setRoleView] = useState<"all" | "customer" | "artisan">("all");
  const [issuedPinByEscrow, setIssuedPinByEscrow] = useState<Record<string, string>>({});
  const [pinInputByEscrow, setPinInputByEscrow] = useState<Record<string, string>>({});
  const [workNotesByEscrow, setWorkNotesByEscrow] = useState<Record<string, string>>({});
  const [disputeReasonByEscrow, setDisputeReasonByEscrow] = useState<Record<string, string>>({});
  const [openDisputeId, setOpenDisputeId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");
  const verifiedReturnRef = useRef(false);

  const { data: escrows, isLoading } = useQuery({
    queryKey: ["escrow-list", roleView, activeOrganization?.id],
    queryFn: () => {
      const qs = roleView !== "all" ? `?role=${roleView}` : "";
      return apiRequest<EscrowTransaction[]>(`/escrow/${qs}`, {
        skipOrgHeader: roleView === "customer" || !activeOrganization,
      });
    },
    enabled: !!user,
  });

  const fundMutation = useMutation({
    mutationFn: (escrowId: string) =>
      apiRequest<EscrowFundResponse>(`/escrow/${escrowId}/fund/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({}),
      }),
    onSuccess: (res) => {
      setActionErr("");
      setActionMsg(res.detail);
      if (res.completion_pin) {
        setIssuedPinByEscrow((prev) => ({ ...prev, [res.escrow.id]: res.completion_pin }));
      }
      queryClient.invalidateQueries({ queryKey: ["escrow-list"] });
    },
    onError: (err) => {
      setActionMsg("");
      setActionErr(err instanceof Error ? err.message : "Could not fund escrow.");
    },
  });

  const submitWorkMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) =>
      apiRequest<EscrowTransaction>(`/escrow/${id}/submit-work/`, {
        method: "POST",
        body: JSON.stringify({ completion_notes: notes }),
      }),
    onSuccess: () => {
      setActionErr("");
      setActionMsg("Work marked completed! Customer has been invited to inspect and release escrow.");
      queryClient.invalidateQueries({ queryKey: ["escrow-list"] });
    },
    onError: (err) => {
      setActionMsg("");
      setActionErr(err instanceof Error ? err.message : "Could not mark work completed.");
    },
  });

  const releaseMutation = useMutation({
    mutationFn: ({ id, pin }: { id: string; pin: string }) =>
      apiRequest<EscrowTransaction>(`/escrow/${id}/release/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({ completion_pin: pin }),
      }),
    onSuccess: () => {
      setActionErr("");
      setActionMsg("Completion confirmed! Full escrow payout has been released to the artisan.");
      queryClient.invalidateQueries({ queryKey: ["escrow-list"] });
    },
    onError: (err) => {
      setActionMsg("");
      setActionErr(err instanceof Error ? err.message : "Could not release escrow.");
    },
  });

  const disputeMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      apiRequest<EscrowTransaction>(`/escrow/${id}/dispute/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      setActionErr("");
      setActionMsg("Dispute raised — funds are now frozen pending Platform Admin arbitration.");
      setOpenDisputeId(null);
      queryClient.invalidateQueries({ queryKey: ["escrow-list"] });
    },
    onError: (err) => {
      setActionMsg("");
      setActionErr(err instanceof Error ? err.message : "Could not open dispute.");
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest<EscrowTransaction>(`/escrow/${id}/cancel/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      setActionErr("");
      setActionMsg("Unfunded escrow contract cancelled.");
      queryClient.invalidateQueries({ queryKey: ["escrow-list"] });
    },
  });

  const verifyReturnMutation = useMutation({
    mutationFn: (reference: string) =>
      apiRequest<{
        processed: boolean;
        detail: string;
        escrow_id?: string | null;
        completion_pin?: string;
      }>("/subscriptions/verify/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({ reference }),
      }),
    onSuccess: (res) => {
      setActionErr("");
      setActionMsg(`Payment confirmed: ${res.detail}`);
      if (res.escrow_id && res.completion_pin) {
        setIssuedPinByEscrow((prev) => ({
          ...prev,
          [res.escrow_id as string]: res.completion_pin as string,
        }));
      }
      queryClient.invalidateQueries({ queryKey: ["escrow-list"] });
    },
    onError: (err) => {
      setActionMsg("");
      setActionErr(err instanceof Error ? err.message : "Could not verify payment.");
    },
  });

  // Verify automatically when returning from Paystack Hosted Checkout
  useEffect(() => {
    if (verifiedReturnRef.current || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("reference") || params.get("trxref");
    if (ref) {
      verifiedReturnRef.current = true;
      verifyReturnMutation.mutate(ref);
      window.history.replaceState({}, "", "/escrow");
    }
  }, [verifyReturnMutation]);

  const heldTotal = (escrows || [])
    .filter((e) => ["funded_held", "work_submitted", "disputed"].includes(e.status))
    .reduce((acc, e) => acc + Number(e.held_in_escrow_amount || 0), 0);
  const releasedTotal = (escrows || [])
    .filter((e) => e.status === "released")
    .reduce((acc, e) => acc + Number(e.artisan_payout_amount || 0), 0);
  const awaitingReleaseCount = (escrows || []).filter((e) => e.status === "work_submitted").length;

  return (
    <div className="space-y-6">
      {/* Velvet Plum Escrow Banner */}
      <div className="relative overflow-hidden rounded-mezer-lg bg-plum px-6 py-6 text-white shadow-card sm:px-8">
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="mezer-eyebrow-light">
              <Lock className="h-3.5 w-3.5 text-brand-300" />
              ArtisanOS Customer Payment Protection
            </div>
            <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-white">
              Escrow Protection Center
            </h1>
            <p className="mt-1 max-w-2xl text-xs text-plum-soft">
              Customers fund into protected escrow and only release full payment using their private
              6-digit Completion PIN after inspecting the finished work.
            </p>
          </div>
          <Link href="/marketplace">
            <Button variant="light" size="sm">
              Find Verified Artisans
            </Button>
          </Link>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-5">
            <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
              Locked in Escrow
            </div>
            <div className="mt-1 text-2xl font-extrabold text-plum">
              {formatCurrency(heldTotal.toFixed(2), activeOrganization?.currency || "NGN")}
            </div>
            <div className="text-xs text-ink-soft">Protected until work is confirmed done</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
              Awaiting Inspection
            </div>
            <div className="mt-1 text-2xl font-extrabold text-brand-700">
              {awaitingReleaseCount}
            </div>
            <div className="text-xs text-ink-soft">Jobs marked done awaiting customer PIN</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <div className="text-xs font-bold uppercase tracking-wider text-ink-faint">
              Total Released Payouts
            </div>
            <div className="mt-1 text-2xl font-extrabold text-emerald-700">
              {formatCurrency(releasedTotal.toFixed(2), activeOrganization?.currency || "NGN")}
            </div>
            <div className="text-xs text-ink-soft">Completed &amp; verified artisan payouts</div>
          </CardContent>
        </Card>
      </div>

      {actionMsg && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800">
          {actionMsg}
        </div>
      )}
      {actionErr && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {actionErr}
        </div>
      )}

      {activeOrganization && (
        <div className="flex w-full rounded-full border border-line bg-white p-1 shadow-mezer-sm sm:inline-flex sm:w-auto">
          {(
            [
              ["all", "All Escrows"],
              ["customer", "As Customer"],
              ["artisan", "As Artisan"],
            ] as const
          ).map(([val, lbl]) => (
            <button
              key={val}
              type="button"
              onClick={() => setRoleView(val)}
              className={`flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors sm:flex-initial sm:px-4 ${
                roleView === val ? "bg-plum text-white" : "text-ink-soft hover:text-plum"
              }`}
            >
              {lbl}
            </button>
          ))}
        </div>
      )}

      {isLoading && <Card className="h-48 animate-pulse bg-white/70" />}

      {!isLoading && (!escrows || escrows.length === 0) ? (
        <Card className="border-dashed border-brand-200 bg-surface-blush">
          <CardContent className="py-12 text-center">
            <ShieldCheck className="mx-auto h-9 w-9 text-brand-700" />
            <h2 className="mt-3 text-base font-bold text-plum">No escrow contracts yet</h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-ink-soft">
              Visit any Verified artisan&apos;s storefront in the Marketplace and click{" "}
              <strong>&ldquo;Hire with Escrow Protection&rdquo;</strong> to lock funds safely until
              your job is completed.
            </p>
            <Link href="/marketplace" className="mt-4 inline-block">
              <Button size="sm">Browse Verified Artisans</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {escrows?.map((esc) => {
            const isCustomer = esc.viewer_role === "customer";
            const isArtisan = esc.viewer_role === "artisan";
            const issuedPin = issuedPinByEscrow[esc.id];
            const payableAmount =
              Number(esc.total_payable_amount) > 0 ? esc.total_payable_amount : esc.total_amount;

            return (
              <Card key={esc.id} className="overflow-hidden">
                <CardHeader className="flex flex-wrap items-start justify-between gap-3 bg-surface/60">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-extrabold text-brand-700">
                        {esc.reference}
                      </span>
                      <StatusBadge status={esc.status} />
                      <span className="rounded-full bg-white px-2.5 py-0.5 text-[10px] font-bold uppercase text-ink-soft">
                        {isCustomer ? "You are Customer" : "You are Artisan"}
                      </span>
                    </div>
                    <h2 className="mt-1.5 text-lg font-extrabold text-plum">{esc.job_title}</h2>
                    <div className="text-xs text-ink-soft">
                      Artisan: <strong>{esc.organization_name}</strong> (
                      {esc.organization_category_label}) · Customer:{" "}
                      <strong>{esc.customer_name}</strong> ({esc.customer_phone})
                    </div>
                  </div>
                  <div className="text-left sm:text-right">
                    <div className="text-xl font-extrabold text-plum">
                      {formatCurrency(esc.total_amount, esc.currency)}
                    </div>
                    <div className="text-[11px] font-semibold text-emerald-700">
                      Held in Escrow: {formatCurrency(esc.held_in_escrow_amount, esc.currency)}
                    </div>
                    {isCustomer ? (
                      <div className="text-[10px] text-ink-faint">
                        + {formatCurrency(esc.customer_protection_fee_amount, esc.currency)} buyer
                        protection · You pay {formatCurrency(payableAmount, esc.currency)}
                      </div>
                    ) : (
                      <div className="text-[10px] text-ink-faint">
                        Net Artisan Payout: {formatCurrency(esc.artisan_payout_amount, esc.currency)}{" "}
                        ({esc.artisan_fee_rate_pct}% service fee)
                      </div>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="space-y-4 p-4 sm:p-5">
                  {esc.job_description && (
                    <p className="text-sm text-ink-soft">{esc.job_description}</p>
                  )}

                  {/* Newly Issued Private 6-Digit Completion PIN Callout (Customer Only) */}
                  {issuedPin && isCustomer && (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-mezer-sm bg-plum p-4 text-white">
                      <div>
                        <div className="inline-flex items-center gap-1.5 text-[11px] font-extrabold uppercase tracking-wider text-[#ffdce6]">
                          <KeyRound className="h-3.5 w-3.5" />
                          Your Private Escrow Completion PIN
                        </div>
                        <div className="mt-1 font-mono text-2xl font-extrabold tracking-[0.25em]">
                          {issuedPin}
                        </div>
                        <p className="mt-1 text-xs text-plum-soft">
                          Save this PIN safely. Enter it ONLY after inspecting and approving the
                          artisan&apos;s completed work.
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="light"
                        onClick={() => navigator.clipboard?.writeText(issuedPin)}
                      >
                        <ClipboardCopy className="h-3.5 w-3.5" /> Copy PIN
                      </Button>
                    </div>
                  )}

                  {esc.artisan_completion_notes && (
                    <div className="rounded-xl border border-purple-200 bg-purple-50 p-3 text-xs text-purple-900">
                      <strong>Artisan Completion Note:</strong> {esc.artisan_completion_notes}
                    </div>
                  )}

                  {esc.dispute_reason && (
                    <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-900">
                      <strong>Dispute Reason:</strong> {esc.dispute_reason}
                      {esc.resolution_notes && (
                        <div className="mt-1">
                          <strong>Platform Admin Resolution:</strong> {esc.resolution_notes}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Role-Specific Action Panels */}
                  {isCustomer && esc.status === "awaiting_funding" && (
                    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/70 p-3.5">
                      <div className="flex-1 text-xs text-amber-900">
                        Fund escrow to lock{" "}
                        <strong>{formatCurrency(esc.total_amount, esc.currency)}</strong> safely
                        (total to pay{" "}
                        <strong>{formatCurrency(payableAmount, esc.currency)}</strong>{" "}
                        including buyer protection). The artisan will be notified to start work
                        immediately, and cannot withdraw until you confirm completion.
                      </div>
                      <Button
                        size="sm"
                        onClick={() => {
                          if (esc.authorization_url && typeof window !== "undefined") {
                            window.location.href = esc.authorization_url;
                          } else {
                            fundMutation.mutate(esc.id);
                          }
                        }}
                        disabled={fundMutation.isPending}
                      >
                        <Lock className="h-3.5 w-3.5" />
                        {fundMutation.isPending ? "Funding..." : "Fund Escrow Safely"}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => cancelMutation.mutate(esc.id)}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}

                  {isArtisan && esc.status === "funded_held" && (
                    <div className="space-y-2.5 rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                      <div className="text-xs font-bold text-emerald-900">
                        Funds Secured in Escrow! Once you finish the job or deliver the goods,
                        submit completion notes below so the customer can inspect &amp; release your
                        payout.
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <Input
                          className="mt-0 bg-white"
                          placeholder="Completion notes (e.g. Installed & tested, zero leaks)..."
                          value={workNotesByEscrow[esc.id] || ""}
                          onChange={(e) =>
                            setWorkNotesByEscrow((prev) => ({ ...prev, [esc.id]: e.target.value }))
                          }
                        />
                        <Button
                          size="sm"
                          className="shrink-0"
                          onClick={() =>
                            submitWorkMutation.mutate({
                              id: esc.id,
                              notes: workNotesByEscrow[esc.id] || "",
                            })
                          }
                          disabled={submitWorkMutation.isPending}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> Mark Work Completed
                        </Button>
                      </div>
                    </div>
                  )}

                  {isCustomer &&
                    (esc.status === "funded_held" || esc.status === "work_submitted") && (
                      <div className="space-y-3 rounded-xl border border-brand-200 bg-surface-blush p-4">
                        <div className="text-xs font-bold text-plum">
                          {esc.status === "work_submitted"
                            ? "Artisan marked this job complete! Inspect the work, then enter your 6-digit Completion PIN to release full payment:"
                            : "Funds are safely locked in escrow. Only release after your work is satisfactorily completed:"}
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                          <Input
                            maxLength={6}
                            className="mt-0 w-full bg-white font-mono tracking-widest sm:w-44"
                            placeholder="6-digit PIN"
                            value={pinInputByEscrow[esc.id] || ""}
                            onChange={(e) =>
                              setPinInputByEscrow((prev) => ({
                                ...prev,
                                [esc.id]: e.target.value,
                              }))
                            }
                          />
                          <Button
                            size="sm"
                            className="w-full sm:w-auto"
                            disabled={
                              releaseMutation.isPending ||
                              (pinInputByEscrow[esc.id] || "").trim().length < 6
                            }
                            onClick={() =>
                              releaseMutation.mutate({
                                id: esc.id,
                                pin: (pinInputByEscrow[esc.id] || "").trim(),
                              })
                            }
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" /> Confirm Work Done &amp; Release
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="w-full sm:w-auto"
                            onClick={() =>
                              setOpenDisputeId(openDisputeId === esc.id ? null : esc.id)
                            }
                          >
                            <AlertTriangle className="h-3.5 w-3.5 text-red-600" /> Raise Dispute
                          </Button>
                        </div>

                        {openDisputeId === esc.id && (
                          <div className="space-y-2 rounded-xl border border-red-200 bg-white p-3">
                            <Label htmlFor={`disp-${esc.id}`}>
                              Why are you freezing escrow funds?
                            </Label>
                            <Textarea
                              id={`disp-${esc.id}`}
                              rows={2}
                              placeholder="Explain clearly (e.g. incomplete work, wrong item, artisan did not show up)..."
                              value={disputeReasonByEscrow[esc.id] || ""}
                              onChange={(e) =>
                                setDisputeReasonByEscrow((prev) => ({
                                  ...prev,
                                  [esc.id]: e.target.value,
                                }))
                              }
                            />
                            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                              <Button
                                size="sm"
                                variant="ghost"
                                className="w-full sm:w-auto"
                                onClick={() => setOpenDisputeId(null)}
                              >
                                Cancel
                              </Button>
                              <Button
                                size="sm"
                                variant="danger"
                                className="w-full sm:w-auto"
                                disabled={disputeMutation.isPending}
                                onClick={() =>
                                  disputeMutation.mutate({
                                    id: esc.id,
                                    reason: disputeReasonByEscrow[esc.id] || "",
                                  })
                                }
                              >
                                Freeze Funds &amp; Submit Dispute
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                  {/* Audit Timeline */}
                  {esc.events && esc.events.length > 0 && (
                    <div className="border-t border-line-soft pt-3">
                      <div className="mb-1.5 text-[10px] font-extrabold uppercase tracking-wider text-ink-faint">
                        Escrow Ledger Timeline
                      </div>
                      <div className="space-y-1">
                        {esc.events.map((ev) => (
                          <div
                            key={ev.id}
                            className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-soft"
                          >
                            <span>
                              <strong className="text-plum">
                                {formatStatusLabel(ev.event_type)}
                              </strong>{" "}
                              — {ev.notes}
                            </span>
                            <span className="text-ink-faint">{formatDateTime(ev.created_at)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function EscrowPage() {
  const { user, activeOrganization, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-soft">
        Loading Escrow Protection...
      </div>
    );
  }

  // Artisans with an active workspace view Escrow inside AppShell; Customers get a clean standalone shell!
  if (activeOrganization) {
    return (
      <AppShell>
        <EscrowContent />
      </AppShell>
    );
  }

  return (
    <div className="min-h-screen bg-surface text-ink">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur-lg">
        <div className="mx-auto flex min-h-[64px] max-w-[1100px] items-center justify-between gap-2 px-4 sm:min-h-[68px] sm:px-5">
          <Link href="/" className="flex min-w-0 items-center gap-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand sm:h-9 sm:w-9">
              <Wrench className="h-4 w-4" />
            </div>
            <span className="truncate text-sm font-extrabold tracking-tight text-plum sm:text-base">
              ArtisanOS Escrow
            </span>
          </Link>
          <div className="flex shrink-0 items-center gap-2">
            <Link href="/marketplace">
              <Button variant="outline" size="sm">
                Nearby Artisans
              </Button>
            </Link>
            <span className="hidden text-xs font-semibold text-plum sm:inline">
              {user.full_name}
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1100px] px-4 py-6 sm:px-5 sm:py-8">
        <EscrowContent />
      </main>
    </div>
  );
}
