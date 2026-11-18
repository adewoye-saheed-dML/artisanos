"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ClipboardCopy, Ruler, Scissors, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import type { PublicFitPassport, UnitSystem } from "@/types/api";

function convertMeasurement(
  numericValue: string | null,
  fromUnit: string,
  targetUnit: UnitSystem
): string {
  if (!numericValue) return "—";
  const num = parseFloat(numericValue);
  if (Number.isNaN(num)) return numericValue;
  if (fromUnit === targetUnit || (fromUnit !== "cm" && fromUnit !== "in")) {
    return `${num.toFixed(2)} ${fromUnit}`;
  }
  const converted = fromUnit === "cm" ? num / 2.54 : num * 2.54;
  return `${converted.toFixed(2)} ${targetUnit}`;
}

export default function PublicFitPassportPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [displayUnit, setDisplayUnit] = useState<UnitSystem>("cm");
  const [copied, setCopied] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["public-fit-passport", token],
    queryFn: () =>
      apiRequest<PublicFitPassport>(`/public/fit/${token}/`, {
        skipOrgHeader: true,
      }),
    enabled: !!token,
    retry: false,
  });

  useEffect(() => {
    if (data?.unit_system) {
      setDisplayUnit(data.unit_system);
    }
  }, [data]);

  return (
    <div className="mezer-hero-bg relative min-h-screen overflow-hidden px-4 py-10">
      <div
        aria-hidden="true"
        className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[480px] w-[480px] rounded-full"
      />
      <div className="relative mx-auto max-w-2xl space-y-6">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
              <Scissors className="h-4 w-4" />
            </div>
            <span className="text-base font-extrabold tracking-tight text-plum">
              ArtisanOS Fit Passport
            </span>
          </Link>
          {data && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                if (typeof window !== "undefined") {
                  navigator.clipboard?.writeText(window.location.href);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }
              }}
            >
              <ClipboardCopy className="h-3.5 w-3.5" />
              {copied ? "Copied link" : "Copy link"}
            </Button>
          )}
        </div>

        {isLoading && <Card className="h-64 animate-pulse bg-white/70" />}

        {error && (
          <Card className="rounded-mezer-lg">
            <CardContent className="py-12 text-center">
              <div className="mezer-eyebrow justify-center">Fit Passport Unavailable</div>
              <h1 className="mt-2 text-xl font-extrabold text-plum">Link expired or revoked</h1>
              <p className="mt-1.5 text-sm text-ink-soft">
                {error instanceof Error
                  ? error.message
                  : "Ask your artisan to issue a fresh Fit Passport link."}
              </p>
            </CardContent>
          </Card>
        )}

        {data && (
          <>
            {/* Velvet Plum Fit Passport Header */}
            <div className="relative overflow-hidden rounded-mezer-lg bg-plum p-7 text-white shadow-phone">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -right-12 -top-12 h-56 w-56 rounded-full bg-brand-500/25 blur-3xl"
              />
              <div className="relative flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mezer-eyebrow-light">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    Verified Portable Fit Passport
                  </div>
                  <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
                    {data.customer_first_name} · {data.profile_label}
                  </h1>
                  <p className="mt-1 text-sm text-plum-soft">
                    Issued by <strong className="text-white">{data.issuing_organization}</strong> ·{" "}
                    {data.template_name} (v{data.version_number})
                  </p>
                </div>

                {/* Live cm/in display switch */}
                <div className="inline-flex rounded-full border border-white/15 bg-plum-surface p-1">
                  {(["cm", "in"] as UnitSystem[]).map((unit) => (
                    <button
                      key={unit}
                      type="button"
                      onClick={() => setDisplayUnit(unit)}
                      className={`rounded-full px-3.5 py-1 text-xs font-bold uppercase transition-colors ${
                        displayUnit === unit
                          ? "bg-brand-600 text-white"
                          : "text-plum-soft hover:text-white"
                      }`}
                    >
                      {unit}
                    </button>
                  ))}
                </div>
              </div>

              <div className="relative mt-5 flex flex-wrap gap-3 text-xs text-plum-soft">
                <span className="rounded-full bg-white/10 px-3 py-1">
                  Recorded: {formatDateTime(data.measured_at)}
                </span>
                <span className="rounded-full bg-white/10 px-3 py-1">
                  Original unit: {data.unit_system.toUpperCase()}
                </span>
                <span className="rounded-full bg-white/10 px-3 py-1">
                  Valid until: {formatDateTime(data.expires_at)}
                </span>
              </div>
            </div>

            <Card className="rounded-mezer-lg">
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <Ruler className="h-4 w-4 text-brand-700" />
                  <h2 className="text-base font-bold text-plum">
                    Measurements ({displayUnit.toUpperCase()})
                  </h2>
                </div>
                <span className="text-xs text-ink-faint">
                  {data.values.length} recorded fields
                </span>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {data.values.map((val) => (
                    <div
                      key={val.id}
                      className="rounded-mezer-sm border border-line-soft bg-surface-blush p-4"
                    >
                      <div className="text-xs font-medium text-ink-soft">{val.field_label}</div>
                      <div className="mt-1 text-lg font-extrabold tracking-tight text-plum">
                        {val.text_value
                          ? val.text_value
                          : convertMeasurement(val.numeric_value, val.unit, displayUnit)}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 flex items-start gap-2.5 rounded-mezer-sm border border-line bg-surface p-4 text-xs text-ink-soft">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" />
                  <p className="leading-relaxed">
                    <strong>Privacy &amp; Fit Notice:</strong> This portable Fit Passport contains
                    only measurement values—no contact details or internal account IDs are exposed.
                    Artisans on ArtisanOS can paste this link to import measurements for review and
                    confirmation prior to cutting.
                  </p>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
