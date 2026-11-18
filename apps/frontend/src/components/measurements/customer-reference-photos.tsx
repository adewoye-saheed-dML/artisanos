"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Eye, History, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  type CaptureQualityReport,
  GuidedCaptureStudio,
} from "@/components/measurements/guided-capture-studio";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime, formatStatusLabel } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  MediaAccessLogItem,
  MediaAsset,
  MediaViewAngle,
  PaginatedResponse,
} from "@/types/api";

export function CustomerReferencePhotosSection({
  customerId,
  activeProfileId,
}: {
  customerId: string;
  activeProfileId?: string | null;
}) {
  const { activeOrganization, activeMembership } = useAuth();
  const queryClient = useQueryClient();

  const canAccessPhotos =
    activeMembership?.role === "owner" ||
    activeMembership?.role === "manager" ||
    activeMembership?.role === "artisan";

  const [showCapture, setShowCapture] = useState(false);
  const [viewingAssetId, setViewingAssetId] = useState<string | null>(null);
  const [viewingBlobUrl, setViewingBlobUrl] = useState<string | null>(null);
  const [viewError, setViewError] = useState("");
  const [auditAssetId, setAuditAssetId] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (viewingBlobUrl) URL.revokeObjectURL(viewingBlobUrl);
    };
  }, [viewingBlobUrl]);

  const { data: mediaData } = useQuery({
    queryKey: ["customer-media", activeOrganization?.id, customerId],
    queryFn: () =>
      apiRequest<PaginatedResponse<MediaAsset>>(`/customers/${customerId}/media/`),
    enabled: !!activeOrganization?.id && !!customerId && canAccessPhotos,
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["customer-media-audit", activeOrganization?.id, customerId, auditAssetId],
    queryFn: () =>
      apiRequest<MediaAccessLogItem[]>(
        `/customers/${customerId}/media/${auditAssetId}/audit/`
      ),
    enabled: !!activeOrganization?.id && !!auditAssetId && canAccessPhotos,
  });

  const uploadMutation = useMutation({
    mutationFn: async (payload: {
      file: File;
      viewAngle: MediaViewAngle;
      photoConsentGranted: boolean;
      qualityMetadata: CaptureQualityReport;
    }) => {
      const form = new FormData();
      form.append("file", payload.file);
      form.append("view_angle", payload.viewAngle);
      form.append("photo_consent_granted", String(payload.photoConsentGranted));
      form.append("quality_metadata", JSON.stringify(payload.qualityMetadata));
      if (activeProfileId) {
        form.append("profile_id", activeProfileId);
      }
      return apiRequest<MediaAsset>(`/customers/${customerId}/media/`, {
        method: "POST",
        body: form,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["customer-media", activeOrganization?.id, customerId],
      });
      setShowCapture(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (assetId: string) =>
      apiRequest<MediaAsset>(`/customers/${customerId}/media/${assetId}/`, {
        method: "DELETE",
      }),
    onSuccess: (_, assetId) => {
      queryClient.invalidateQueries({
        queryKey: ["customer-media", activeOrganization?.id, customerId],
      });
      if (viewingAssetId === assetId) {
        if (viewingBlobUrl) URL.revokeObjectURL(viewingBlobUrl);
        setViewingAssetId(null);
        setViewingBlobUrl(null);
      }
      if (auditAssetId === assetId) {
        queryClient.invalidateQueries({
          queryKey: ["customer-media-audit", activeOrganization?.id, customerId, assetId],
        });
      }
    },
  });

  async function openProtectedPhoto(asset: MediaAsset) {
    if (!activeOrganization?.id) return;
    setViewError("");
    try {
      const res = await fetch(
        `/api/v1/customers/${customerId}/media/${asset.id}/content/`,
        {
          method: "GET",
          credentials: "include",
          headers: {
            "X-Organization-Id": activeOrganization.id,
          },
        }
      );
      if (!res.ok) {
        throw new Error(`Could not load photo (${res.status})`);
      }
      const blob = await res.blob();
      if (viewingBlobUrl) URL.revokeObjectURL(viewingBlobUrl);
      const nextUrl = URL.createObjectURL(blob);
      setViewingBlobUrl(nextUrl);
      setViewingAssetId(asset.id);
      queryClient.invalidateQueries({
        queryKey: ["customer-media-audit", activeOrganization?.id, customerId, asset.id],
      });
    } catch (err) {
      setViewError(err instanceof Error ? err.message : "Failed to load protected photo.");
    }
  }

  if (!canAccessPhotos) {
    return null;
  }

  const assets = mediaData?.results || [];

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-blush text-brand-700">
            <Camera className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-plum">Guided Reference Photos</h2>
            <p className="text-xs text-ink-faint">
              Consented front/side photos for visual fit review · 30-day retention · access logged
            </p>
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={() => setShowCapture((v) => !v)}>
          {showCapture ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
          {showCapture ? "Close capture" : "Capture / upload photo"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-4">
        {showCapture && (
          <div className="rounded-mezer-sm border border-line bg-paper p-4">
            <GuidedCaptureStudio
              organizationName={activeOrganization?.name || "this workshop"}
              isUploading={uploadMutation.isPending}
              onUpload={async (payload) => {
                await uploadMutation.mutateAsync(payload);
              }}
            />
          </div>
        )}

        {viewError && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2 text-xs text-red-700">
            {viewError}
          </div>
        )}

        {viewingBlobUrl && viewingAssetId && (
          <div className="rounded-mezer-sm border border-brand-300 bg-plum p-4 text-white">
            <div className="mb-3 flex items-center justify-between">
              <span className="mezer-eyebrow-light">Protected Photo Preview (View Logged)</span>
              <Button
                size="sm"
                variant="light"
                onClick={() => {
                  URL.revokeObjectURL(viewingBlobUrl);
                  setViewingBlobUrl(null);
                  setViewingAssetId(null);
                }}
              >
                Close preview
              </Button>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={viewingBlobUrl}
              alt="Customer reference photo"
              className="mx-auto max-h-96 rounded-xl object-contain"
            />
          </div>
        )}

        {auditAssetId && auditLogs && (
          <div className="rounded-mezer-sm border border-line bg-surface p-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-extrabold uppercase tracking-wider text-plum">
                <History className="h-3.5 w-3.5 text-brand-700" />
                Photo Access Audit Trail
              </div>
              <Button size="sm" variant="ghost" onClick={() => setAuditAssetId(null)}>
                Close
              </Button>
            </div>
            <div className="divide-y divide-line-soft text-xs">
              {auditLogs.map((log) => (
                <div key={log.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div>
                    <span className="font-bold uppercase text-brand-700">{log.action}</span>{" "}
                    <span className="text-ink-soft">
                      {log.accessed_by_name ? `by ${log.accessed_by_name}` : "via public portal"}
                    </span>
                    {log.notes && <span className="text-ink-faint"> · {log.notes}</span>}
                  </div>
                  <span className="text-ink-faint">{formatDateTime(log.created_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {assets.length === 0 ? (
          <p className="text-sm text-ink-faint">
            No reference photos stored for this customer. Capture front/side views with explicit
            consent when helpful for posture review.
          </p>
        ) : (
          <div className="divide-y divide-line-soft rounded-mezer-sm border border-line">
            {assets.map((asset) => (
              <div
                key={asset.id}
                className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-plum">
                      {formatStatusLabel(asset.view_angle)}
                    </span>
                    <StatusBadge status={asset.status} />
                  </div>
                  <div className="mt-0.5 text-xs text-ink-faint">
                    Uploaded {formatDateTime(asset.created_at)}
                    {asset.status === "active"
                      ? ` · Auto-expires ${formatDateTime(asset.retention_expires_at)}`
                      : asset.deleted_at
                      ? ` · Deleted ${formatDateTime(asset.deleted_at)}`
                      : ""}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {asset.status === "active" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void openProtectedPhoto(asset)}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      View (logged)
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setAuditAssetId(asset.id)}
                  >
                    Audit log
                  </Button>
                  {asset.status === "active" && (
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(asset.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete file
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
