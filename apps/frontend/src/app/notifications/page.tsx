"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bell, CheckCheck } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { NotificationListResponse } from "@/types/api";

export default function NotificationsPage() {
  const { activeOrganization } = useAuth();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", activeOrganization?.id],
    queryFn: () => apiRequest<NotificationListResponse>("/notifications/"),
    enabled: !!activeOrganization?.id,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) =>
      apiRequest(`/notifications/${id}/read/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-badge"] });
    },
  });

  const markAllMutation = useMutation({
    mutationFn: () =>
      apiRequest("/notifications/read-all/", {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-badge"] });
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Activity Inbox</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Notifications
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Real-time alerts for customer measurements, order milestones, low stock, and storefront
              inquiries.
            </p>
          </div>
          {(data?.unread_count ?? 0) > 0 && (
            <Button
              size="sm"
              variant="outline"
              disabled={markAllMutation.isPending}
              onClick={() => markAllMutation.mutate()}
            >
              <CheckCheck className="h-4 w-4" />
              Mark all read ({data?.unread_count})
            </Button>
          )}
        </div>

        {isLoading && <Card className="h-48 animate-pulse bg-white/70" />}

        {data && data.results.length === 0 && (
          <Card className="border-dashed border-brand-200 bg-surface-blush">
            <CardContent className="py-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-white text-brand-700 shadow-mezer-sm">
                <Bell className="h-6 w-6" />
              </div>
              <h2 className="mt-3 text-base font-bold text-plum">All caught up</h2>
              <p className="mt-1 text-sm text-ink-soft">
                New customer measurement submissions, order confirmations, and storefront inquiries
                will appear here automatically.
              </p>
            </CardContent>
          </Card>
        )}

        {data && data.results.length > 0 && (
          <Card className="overflow-hidden">
            <div className="divide-y divide-line-soft">
              {data.results.map((item) => (
                <div
                  key={item.id}
                  className={`flex flex-wrap items-start justify-between gap-4 px-6 py-4 transition-colors ${
                    item.is_read ? "bg-white" : "bg-surface-blush"
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {!item.is_read && <span className="h-2 w-2 rounded-full bg-brand-600" />}
                      <span className="text-sm font-bold text-plum">{item.title}</span>
                      <span className="rounded-full border border-line bg-white px-2.5 py-0.5 text-[10px] font-semibold text-ink-faint">
                        {formatStatusLabel(item.event_type)}
                      </span>
                    </div>
                    {item.message && <p className="text-sm text-ink-soft">{item.message}</p>}
                    <div className="text-xs text-ink-faint">{formatDateTime(item.created_at)}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!item.is_read && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => markReadMutation.mutate(item.id)}
                      >
                        Mark read
                      </Button>
                    )}
                    {item.link_path && (
                      <Link href={item.link_path}>
                        <Button size="sm" variant="outline">
                          Open <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
