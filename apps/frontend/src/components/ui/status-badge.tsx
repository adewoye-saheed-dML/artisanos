import { cn, formatStatusLabel } from "@/lib/utils";

const STATUS_STYLE_MAP: Record<string, string> = {
  draft: "bg-surface text-ink-soft border-line",
  awaiting_measurements: "bg-amber-50 text-amber-800 border-amber-200",
  quoted: "bg-brand-50 text-brand-700 border-brand-200",
  confirmed: "bg-brand-100/80 text-brand-900 border-brand-300",
  in_production: "bg-purple-50 text-purple-800 border-purple-200",
  fitting: "bg-rose-50 text-rose-800 border-rose-200",
  ready: "bg-emerald-50 text-emerald-800 border-emerald-200",
  completed: "bg-emerald-100 text-emerald-900 border-emerald-300",
  cancelled: "bg-red-50 text-red-700 border-red-200",
  on_hold: "bg-amber-50 text-amber-900 border-amber-200",
  verified: "bg-emerald-50 text-emerald-800 border-emerald-200",
  submitted: "bg-brand-50 text-brand-700 border-brand-200",
  needs_review: "bg-amber-50 text-amber-800 border-amber-200",
  superseded: "bg-surface text-ink-faint border-line",
  pending: "bg-amber-50 text-amber-800 border-amber-200",
  expired: "bg-surface text-ink-faint border-line",
  revoked: "bg-red-50 text-red-700 border-red-200",
  paid: "bg-emerald-50 text-emerald-800 border-emerald-200",
  partial: "bg-amber-50 text-amber-800 border-amber-200",
  unpaid: "bg-surface text-ink-soft border-line",
  active: "bg-emerald-50 text-emerald-800 border-emerald-200",
  suspended: "bg-red-50 text-red-700 border-red-200",
  accepted: "bg-emerald-50 text-emerald-800 border-emerald-200",
  todo: "bg-surface text-ink-soft border-line",
  in_progress: "bg-brand-50 text-brand-700 border-brand-200",
  blocked: "bg-red-50 text-red-700 border-red-200",
  done: "bg-emerald-50 text-emerald-800 border-emerald-200",
  scheduled: "bg-brand-50 text-brand-700 border-brand-200",
  no_show: "bg-amber-50 text-amber-800 border-amber-200",
  published: "bg-emerald-50 text-emerald-800 border-emerald-200",
  archived: "bg-surface text-ink-faint border-line",
  new: "bg-brand-100/80 text-brand-900 border-brand-300",
  contacted: "bg-amber-50 text-amber-800 border-amber-200",
  converted: "bg-emerald-50 text-emerald-800 border-emerald-200",
  closed: "bg-surface text-ink-faint border-line",
  succeeded: "bg-emerald-50 text-emerald-800 border-emerald-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  refunded: "bg-amber-50 text-amber-800 border-amber-200",
  trialing: "bg-brand-50 text-brand-700 border-brand-200",
  past_due: "bg-red-50 text-red-700 border-red-200",
  unsubmitted: "bg-surface text-ink-soft border-line",
  pending_review: "bg-amber-50 text-amber-800 border-amber-200",
  approved: "bg-emerald-50 text-emerald-800 border-emerald-200",
  rejected: "bg-red-50 text-red-700 border-red-200",
  awaiting_funding: "bg-amber-50 text-amber-800 border-amber-200",
  funded_held: "bg-brand-100/80 text-brand-900 border-brand-300",
  work_submitted: "bg-purple-50 text-purple-800 border-purple-200",
  released: "bg-emerald-100 text-emerald-900 border-emerald-300",
  disputed: "bg-red-100 text-red-800 border-red-300",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const tone = STATUS_STYLE_MAP[status] || "bg-surface text-ink-soft border-line";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-tight sm:px-3 sm:text-xs",
        tone,
        className
      )}
    >
      {formatStatusLabel(status)}
    </span>
  );
}
