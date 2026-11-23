"use client";

import { Camera, CheckCircle2, Info, ShieldCheck, Sun, Upload, VideoOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/form-controls";
import type { MediaViewAngle } from "@/types/api";

export interface CaptureQualityReport {
  width: number;
  height: number;
  brightness_score: number;
  lighting_ok: boolean;
  resolution_ok: boolean;
  framing_confirmed: boolean;
}

interface GuidedCaptureStudioProps {
  organizationName: string;
  onUpload: (payload: {
    file: File;
    viewAngle: MediaViewAngle;
    photoConsentGranted: boolean;
    qualityMetadata: CaptureQualityReport;
  }) => Promise<void>;
  isUploading?: boolean;
}

async function analyzeImageBlob(blob: Blob): Promise<CaptureQualityReport> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const width = img.naturalWidth;
      const height = img.naturalHeight;
      const canvas = document.createElement("canvas");
      const sampleW = 64;
      const sampleH = 64;
      canvas.width = sampleW;
      canvas.height = sampleH;
      const ctx = canvas.getContext("2d");
      let brightness = 128;
      if (ctx) {
        ctx.drawImage(img, 0, 0, sampleW, sampleH);
        const pixels = ctx.getImageData(0, 0, sampleW, sampleH).data;
        let sum = 0;
        const count = pixels.length / 4;
        for (let i = 0; i < pixels.length; i += 4) {
          sum += 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2];
        }
        brightness = Math.round(sum / Math.max(count, 1));
      }
      URL.revokeObjectURL(url);
      resolve({
        width,
        height,
        brightness_score: brightness,
        lighting_ok: brightness >= 55 && brightness <= 230,
        resolution_ok: width >= 400 && height >= 400,
        framing_confirmed: true,
      });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve({
        width: 0,
        height: 0,
        brightness_score: 0,
        lighting_ok: false,
        resolution_ok: false,
        framing_confirmed: false,
      });
    };
    img.src = url;
  });
}

export function GuidedCaptureStudio({
  organizationName,
  onUpload,
  isUploading = false,
}: GuidedCaptureStudioProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [viewAngle, setViewAngle] = useState<MediaViewAngle>("front");
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [quality, setQuality] = useState<CaptureQualityReport | null>(null);
  const [framingConfirmed, setFramingConfirmed] = useState(false);
  const [photoConsent, setPhotoConsent] = useState(false);
  const [uploadError, setUploadError] = useState("");

  useEffect(() => {
    return () => {
      stopCamera();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setCameraActive(false);
  }

  async function startCamera() {
    setCameraError("");
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setCameraError("Camera API is unavailable on this browser. Use photo upload below.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1080 }, height: { ideal: 1440 } },
        audio: false,
      });
      streamRef.current = stream;
      setCameraActive(true);
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play();
        }
      }, 60);
    } catch (err) {
      setCameraError(
        err instanceof Error
          ? `Camera permission unavailable (${err.message}). You can upload a photo directly below.`
          : "Camera permission denied. Upload a photo directly below."
      );
    }
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 720;
    canvas.height = video.videoHeight || 1280;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      async (blob) => {
        if (!blob) return;
        const file = new File([blob], `guided_${viewAngle}_${Date.now()}.jpg`, {
          type: "image/jpeg",
        });
        await handleSelectedFile(file);
        stopCamera();
      },
      "image/jpeg",
      0.9
    );
  }

  async function handleSelectedFile(file: File) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const nextUrl = URL.createObjectURL(file);
    setCapturedFile(file);
    setPreviewUrl(nextUrl);
    setUploadError("");
    const report = await analyzeImageBlob(file);
    setQuality(report);
  }

  async function handleSubmit() {
    if (!capturedFile) {
      setUploadError("Capture or choose a reference photo first.");
      return;
    }
    if (!photoConsent) {
      setUploadError("Explicit photo consent is required before uploading.");
      return;
    }
    setUploadError("");
    try {
      await onUpload({
        file: capturedFile,
        viewAngle,
        photoConsentGranted: photoConsent,
        qualityMetadata: {
          ...(quality || {
            width: 0,
            height: 0,
            brightness_score: 0,
            lighting_ok: false,
            resolution_ok: false,
          }),
          framing_confirmed: framingConfirmed,
        },
      });
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setCapturedFile(null);
      setPreviewUrl(null);
      setQuality(null);
      setFramingConfirmed(false);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Could not upload reference photo.");
    }
  }

  return (
    <div className="space-y-4">
      {/* Honest Phase 4 Milestone 1 Notice */}
      <div className="flex items-start gap-2.5 rounded-mezer-sm border border-brand-200 bg-surface-blush p-3.5 text-xs text-ink">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
        <p className="leading-relaxed">
          <strong>Guided Reference Capture (No Automated AI Sizing):</strong> Photos attach to a
          pending artisan review so your tailor can verify posture and fit visually. Automated
          computer-vision measurement estimation is intentionally disabled until independently
          validated.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="capture-angle">Capture angle</Label>
          <Select
            id="capture-angle"
            value={viewAngle}
            onChange={(e) => setViewAngle(e.target.value as MediaViewAngle)}
          >
            <option value="front">Step 1 · Front View (Full body)</option>
            <option value="side">Step 2 · Side Profile (Full body)</option>
            <option value="back">Back View</option>
            <option value="detail">Fit / Posture Detail</option>
          </Select>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end">
          {!cameraActive ? (
            <Button size="sm" variant="outline" className="w-full sm:w-auto" onClick={startCamera}>
              <Camera className="h-4 w-4" />
              Open guided camera
            </Button>
          ) : (
            <Button size="sm" variant="ghost" className="w-full sm:w-auto" onClick={stopCamera}>
              <VideoOff className="h-4 w-4" />
              Close camera
            </Button>
          )}
          <label className="inline-flex min-h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-full border border-line bg-white px-4 py-2 text-xs font-semibold text-ink hover:border-brand-300 hover:bg-surface-blush sm:w-auto">
            <Upload className="h-3.5 w-3.5 shrink-0" />
            Choose image file
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void handleSelectedFile(f);
              }}
            />
          </label>
        </div>
      </div>

      {cameraError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900">
          {cameraError}
        </div>
      )}

      {/* Live Guided Camera Viewfinder with Silhouette Overlay */}
      {cameraActive && (
        <div className="relative mx-auto max-w-sm overflow-hidden rounded-mezer-md border-2 border-brand-500 bg-plum shadow-phone">
          <video
            ref={videoRef}
            playsInline
            muted
            className="aspect-[3/4] w-full object-cover"
          />
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <svg
              viewBox="0 0 200 320"
              className="h-[82%] w-[70%] stroke-brand-300/80"
              fill="none"
              strokeWidth="2"
              strokeDasharray="6 6"
            >
              {viewAngle === "side" ? (
                <>
                  <circle cx="100" cy="42" r="22" />
                  <path d="M90 66 L112 72 L118 160 L110 295 M88 160 L92 295" />
                </>
              ) : (
                <>
                  <circle cx="100" cy="42" r="22" />
                  <path d="M56 82 Q100 66 144 82 L152 170 L132 170 L126 112 L124 295 M74 112 L76 295 M56 82 L48 170 L68 170" />
                </>
              )}
            </svg>
          </div>
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-plum/85 px-4 py-3 text-white backdrop-blur-sm">
            <span className="text-xs font-semibold">
              Stand ~2m back · Full body inside outline
            </span>
            <Button size="sm" onClick={captureFrame}>
              Capture
            </Button>
          </div>
        </div>
      )}

      {/* Preview + Real Client-Side Quality Checks */}
      {previewUrl && quality && (
        <div className="grid gap-4 rounded-mezer-sm border border-line bg-white p-4 sm:grid-cols-[160px_1fr]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt="Guided capture preview"
            className="h-44 w-full rounded-xl border border-line-soft object-cover"
          />
          <div className="space-y-3">
            <div className="text-xs font-extrabold uppercase tracking-wider text-brand-700">
              Capture Quality Check ({viewAngle})
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 font-semibold ${
                  quality.resolution_ok
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-amber-50 text-amber-800"
                }`}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                {quality.width}×{quality.height}px
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 font-semibold ${
                  quality.lighting_ok
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-amber-50 text-amber-800"
                }`}
              >
                <Sun className="h-3.5 w-3.5" />
                Lighting {quality.lighting_ok ? "Good" : "Check brightness"} (
                {quality.brightness_score}/255)
              </span>
            </div>

            <label className="flex items-start gap-2 text-xs text-ink-soft">
              <input
                type="checkbox"
                className="mt-0.5 accent-brand-700"
                checked={framingConfirmed}
                onChange={(e) => setFramingConfirmed(e.target.checked)}
              />
              <span>
                Framing &amp; pose confirmed: upright posture, fitted clothing, full target area
                clearly visible.
              </span>
            </label>
          </div>
        </div>
      )}

      {/* Explicit Photo Privacy Consent */}
      <label className="flex items-start gap-3 rounded-mezer-sm border border-brand-200 bg-surface-blush p-3.5 text-xs text-ink">
        <input
          type="checkbox"
          className="mt-0.5 accent-brand-700"
          checked={photoConsent}
          onChange={(e) => setPhotoConsent(e.target.checked)}
        />
        <span className="leading-relaxed">
          <span className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-brand-700">
            <ShieldCheck className="h-3.5 w-3.5" /> Explicit Photo Consent (30-Day Retention)
          </span>
          Customer explicitly consents to {organizationName} storing this reference photo solely for
          fitting review. Access is restricted to authorized workshop artisans, every view is
          logged, images are <strong>never</strong> used for AI training, and files expire
          automatically after 30 days (or on immediate deletion).
        </span>
      </label>

      {uploadError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-700">
          {uploadError}
        </div>
      )}

      <div className="flex justify-end">
        <Button
          size="sm"
          className="w-full sm:w-auto"
          onClick={handleSubmit}
          disabled={isUploading || !capturedFile}
        >
          {isUploading ? "Uploading securely..." : "Save consented reference photo"}
        </Button>
      </div>
    </div>
  );
}
