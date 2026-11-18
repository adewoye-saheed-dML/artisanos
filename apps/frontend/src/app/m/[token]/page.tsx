"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Camera, CheckCircle2, Scissors, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  type CaptureQualityReport,
  GuidedCaptureStudio,
} from "@/components/measurements/guided-capture-studio";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import type { MediaViewAngle, PublicMeasurementRequest, UnitSystem } from "@/types/api";

export default function PublicMeasurementPortalPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const [unitSystem, setUnitSystem] = useState<UnitSystem>("cm");
  const [valuesMap, setValuesMap] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [consentGranted, setConsentGranted] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [showPhotoCapture, setShowPhotoCapture] = useState(false);
  const [uploadedAngles, setUploadedAngles] = useState<string[]>([]);

  const photoUploadMutation = useMutation({
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
      return apiRequest<{ view_angle: string }>(`/public/measurement-requests/${token}/photos/`, {
        method: "POST",
        skipOrgHeader: true,
        body: form,
      });
    },
    onSuccess: (res) => {
      setUploadedAngles((prev) => [...prev, res.view_angle]);
    },
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-measurement-request", token],
    queryFn: () =>
      apiRequest<PublicMeasurementRequest>(`/public/measurement-requests/${token}/`, {
        skipOrgHeader: true,
      }),
    enabled: !!token,
    retry: false,
  });

  useEffect(() => {
    if (data?.preferred_unit) {
      setUnitSystem(data.preferred_unit);
    }
  }, [data]);

  const submitMutation = useMutation({
    mutationFn: () => {
      const payloadValues = (data?.fields || [])
        .map((f) => {
          const raw = (valuesMap[f.key] || "").trim();
          if (!raw) return null;
          if (f.unit_type === "text") {
            return { field_key: f.key, text_value: raw };
          }
          return { field_key: f.key, numeric_value: raw };
        })
        .filter(Boolean);

      return apiRequest(`/public/measurement-requests/${token}/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          unit_system: unitSystem,
          notes,
          consent_granted: consentGranted,
          values: payloadValues,
        }),
      });
    },
    onSuccess: () => {
      setSubmitError("");
      setSubmitted(true);
    },
    onError: (err) => {
      setSubmitError(err instanceof Error ? err.message : "Could not submit measurements.");
    },
  });

  return (
    <div className="mezer-hero-bg relative min-h-screen overflow-hidden px-4 py-10">
      <div
        aria-hidden="true"
        className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[460px] w-[460px] rounded-full"
      />
      <div className="relative mx-auto max-w-2xl">
        <div className="mb-7 flex items-center justify-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Scissors className="h-5 w-5" />
          </div>
          <span className="text-lg font-extrabold tracking-tight text-plum">
            ArtisanOS Fit Portal
          </span>
        </div>

        {isLoading && <Card className="h-48 animate-pulse bg-white/70" />}

        {error && (
          <Card className="rounded-mezer-lg">
            <CardContent className="py-12 text-center">
              <div className="mezer-eyebrow justify-center">Link Expired or Used</div>
              <h1 className="mt-2 text-xl font-extrabold text-plum">
                Measurement link unavailable
              </h1>
              <p className="mt-1.5 text-sm text-ink-soft">
                {error instanceof Error ? error.message : "This link has expired or been used."}
              </p>
            </CardContent>
          </Card>
        )}

        {submitted && (
          <Card className="rounded-mezer-lg">
            <CardContent className="py-12 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
                <CheckCircle2 className="h-8 w-8" />
              </div>
              <div className="mezer-eyebrow mt-4 justify-center">Received</div>
              <h1 className="mt-1 text-2xl font-extrabold text-plum">Measurements Submitted</h1>
              <p className="mx-auto mt-2 max-w-md text-sm text-ink-soft">
                Thank you! {data?.organization_name} will review and confirm your measurements
                before cutting or production.
              </p>
            </CardContent>
          </Card>
        )}

        {data && !submitted && (
          <Card className="rounded-mezer-lg">
            <CardHeader>
              <div className="mezer-eyebrow">Secure Measurement Request</div>
              <h1 className="mt-1.5 text-xl font-extrabold tracking-tight text-plum sm:text-2xl">
                Hi {data.customer_first_name}, share your fit for {data.organization_name}
              </h1>
              <p className="mt-1 text-sm text-ink-soft">
                Template: <span className="font-semibold text-ink">{data.template_name}</span>.
                Every submission is reviewed and confirmed by your artisan before production.
              </p>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-5"
                onSubmit={(e) => {
                  e.preventDefault();
                  submitMutation.mutate();
                }}
              >
                {submitError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {submitError}
                  </div>
                )}

                <div className="max-w-xs">
                  <Label htmlFor="pub-unit">Measurement unit</Label>
                  <Select
                    id="pub-unit"
                    value={unitSystem}
                    onChange={(e) => setUnitSystem(e.target.value as UnitSystem)}
                  >
                    <option value="cm">Centimetres (cm)</option>
                    <option value="in">Inches (in)</option>
                  </Select>
                </div>

                <div className="grid gap-3.5 sm:grid-cols-2">
                  {data.fields.map((field) => (
                    <div
                      key={field.id}
                      className="rounded-mezer-sm border border-line bg-surface-blush p-3.5"
                    >
                      <Label htmlFor={`pub-${field.key}`} className="flex items-center justify-between">
                        <span className="text-ink">
                          {field.label}
                          {field.is_required && <span className="ml-1 text-brand-600">*</span>}
                        </span>
                        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold uppercase text-brand-700">
                          {field.unit_type === "text" ? "text" : unitSystem}
                        </span>
                      </Label>
                      <Input
                        id={`pub-${field.key}`}
                        type={field.unit_type === "text" ? "text" : "number"}
                        step={field.unit_type === "text" ? undefined : "0.01"}
                        required={field.is_required}
                        className="mt-2 bg-white"
                        value={valuesMap[field.key] || ""}
                        onChange={(e) =>
                          setValuesMap((prev) => ({ ...prev, [field.key]: e.target.value }))
                        }
                      />
                      {field.guidance_text && (
                        <p className="mt-1.5 text-xs text-ink-faint">{field.guidance_text}</p>
                      )}
                    </div>
                  ))}
                </div>

                <div>
                  <Label htmlFor="pub-notes">Notes for your artisan (optional)</Label>
                  <Textarea
                    id="pub-notes"
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>

                {/* Optional Guided Reference Photo Capture */}
                <div className="rounded-mezer-sm border border-line bg-paper p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Camera className="h-4 w-4 text-brand-700" />
                      <span className="text-sm font-bold text-plum">
                        Optional: Attach Guided Front / Side Photos
                      </span>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowPhotoCapture((v) => !v)}
                    >
                      {showPhotoCapture ? "Hide camera" : "Add reference photo"}
                    </Button>
                  </div>
                  {uploadedAngles.length > 0 && (
                    <p className="mt-2 text-xs font-semibold text-emerald-700">
                      Attached reference photo(s): {uploadedAngles.join(", ")} (will link to your
                      measurement review)
                    </p>
                  )}
                  {showPhotoCapture && (
                    <div className="mt-4 border-t border-line-soft pt-4">
                      <GuidedCaptureStudio
                        organizationName={data.organization_name}
                        isUploading={photoUploadMutation.isPending}
                        onUpload={async (payload) => {
                          await photoUploadMutation.mutateAsync(payload);
                        }}
                      />
                    </div>
                  )}
                </div>

                <label className="flex items-start gap-3 rounded-mezer-sm border border-brand-200 bg-surface-blush p-4 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={consentGranted}
                    onChange={(e) => setConsentGranted(e.target.checked)}
                    className="mt-1 accent-brand-700"
                  />
                  <span className="flex-1 leading-relaxed">
                    <span className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-brand-700">
                      <ShieldCheck className="h-3.5 w-3.5" /> Explicit Consent
                    </span>
                    I consent to {data.organization_name} storing these body measurements solely to
                    fulfil and tailor my custom orders.
                  </span>
                </label>

                <Button
                  type="submit"
                  size="lg"
                  className="w-full"
                  disabled={submitMutation.isPending}
                >
                  {submitMutation.isPending ? "Submitting..." : "Submit measurements"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
