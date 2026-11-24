"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, MapPin, Navigation, Phone, ShieldCheck, Store, UserCheck, Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  type DetectedLocationMeta,
  NigeriaLocationPicker,
  type NigeriaLocationValue,
} from "@/components/locations/nigeria-location-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { ARTISAN_CATEGORIES, ORG_CATEGORY_VALUES } from "@/lib/artisans";
import { useAuth } from "@/providers/auth-provider";
import type { MarketplaceStorefrontCard, User } from "@/types/api";

const registerSchema = z.object({
  full_name: z.string().min(2, "Full name is required."),
  email: z.string().email("Enter a valid email address."),
  phone: z.string().min(7, "Provide a valid phone / WhatsApp number."),
  password: z.string().min(8, "Password must be at least 8 characters."),
  organization_name: z.string().optional(),
  organization_category: z.enum(ORG_CATEGORY_VALUES),
  currency: z.string().length(3, "Use a 3-letter currency code (e.g. NGN, USD)."),
  preferred_unit: z.enum(["cm", "in"]),
  landmark: z.string().optional(),
  callout_fee: z.string().optional(),
  skills_text: z.string().optional(),
  available_for_callout: z.boolean().optional(),
  // Strict Anti-Scam KYC fields (enforced for artisans)
  nin: z.string().optional(),
  government_id_type: z.enum(["nin_slip", "voters_card", "drivers_license", "intl_passport"]).optional(),
  cac_number: z.string().optional(),
  cac_business_name: z.string().optional(),
  guarantor_name: z.string().optional(),
  guarantor_phone: z.string().optional(),
  bank_name: z.string().optional(),
  bank_account_number: z.string().optional(),
  bank_account_name: z.string().optional(),
});

type RegisterValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [accountType, setAccountType] = useState<"artisan" | "customer">("artisan");
  const [serverError, setServerError] = useState("");
  const [location, setLocation] = useState<NigeriaLocationValue>({
    stateId: "",
    lgaId: "",
    wardId: "",
    pollingUnitId: "",
  });
  const [detectedCoords, setDetectedCoords] = useState<{ lat?: string; lng?: string }>({});

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      organization_category: "tailor",
      currency: "NGN",
      preferred_unit: "cm",
      available_for_callout: true,
      government_id_type: "nin_slip",
    },
  });

  useEffect(() => {
    if (user) {
      if (user.memberships.length > 0) {
        router.replace("/dashboard");
      } else {
        const params = new URLSearchParams();
        if (user.state) params.set("state", user.state);
        if (user.lga) params.set("lga", user.lga);
        if (user.ward) params.set("ward", user.ward);
        if (user.polling_unit) params.set("polling_unit", user.polling_unit);
        router.replace(`/marketplace${params.toString() ? `?${params.toString()}` : ""}`);
      }
    }
  }, [user, router]);

  // Live preview of nearby artisans springing up as soon as Ward / Polling Unit is detected or picked
  const hasLocation = !!(
    location.stateId ||
    location.lgaId ||
    location.wardId ||
    location.pollingUnitId
  );
  const { data: nearbyPreview } = useQuery({
    queryKey: ["register-nearby-preview", location],
    queryFn: () => {
      const params = new URLSearchParams();
      if (location.stateId) params.set("state", location.stateId);
      if (location.lgaId) params.set("lga", location.lgaId);
      if (location.wardId) params.set("ward", location.wardId);
      if (location.pollingUnitId) params.set("polling_unit", location.pollingUnitId);
      return apiRequest<MarketplaceStorefrontCard[]>(
        `/marketplace/artisans/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
    enabled: hasLocation,
  });

  function handleDetectedMeta(meta: DetectedLocationMeta) {
    if (meta.landmark) {
      setValue("landmark", meta.landmark);
    }
    if (meta.latitude && meta.longitude) {
      setDetectedCoords({ lat: meta.latitude, lng: meta.longitude });
    }
  }

  async function onSubmit(values: RegisterValues) {
    setServerError("");
    if (accountType === "artisan") {
      if (!values.organization_name || values.organization_name.trim().length < 2) {
        setServerError("Please enter your business or workshop name (at least 2 characters).");
        return;
      }
      const cleanNin = (values.nin || "").replace(/[\s-]+/g, "");
      if (!/^\d{11}$/.test(cleanNin)) {
        setServerError("Strict Anti-Scam KYC: Enter a valid 11-digit Nigerian NIN to register as an artisan.");
        return;
      }
      const cleanCac = (values.cac_number || "").replace(/[\s-]+/g, "").toUpperCase();
      if (cleanCac && !/^(RC|BN|IT)\d{5,9}$/.test(cleanCac)) {
        setServerError("CAC number must start with RC, BN, or IT followed by 5–9 digits (e.g. RC1234567).");
        return;
      }
      const cleanNuban = (values.bank_account_number || "").replace(/[\s-]+/g, "");
      if (cleanNuban && !/^\d{10}$/.test(cleanNuban)) {
        setServerError("Payout bank account number must be a 10-digit Nigerian NUBAN.");
        return;
      }
    }

    const skills = (values.skills_text || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      const payload: Record<string, unknown> = {
        full_name: values.full_name,
        email: values.email,
        phone: values.phone,
        password: values.password,
        country: "Nigeria",
        state: location.stateId || null,
        lga: location.lgaId || null,
        ward: location.wardId || null,
        polling_unit: location.pollingUnitId || null,
        landmark: values.landmark || "",
        latitude: detectedCoords.lat || null,
        longitude: detectedCoords.lng || null,
      };

      if (accountType === "artisan") {
        payload.organization_name = values.organization_name?.trim();
        payload.organization_category = values.organization_category;
        payload.currency = values.currency.toUpperCase();
        payload.preferred_unit = values.preferred_unit;
        payload.available_for_callout = values.available_for_callout ?? true;
        payload.callout_fee = values.callout_fee?.trim() ? values.callout_fee.trim() : null;
        payload.skills = skills;
        payload.nin = (values.nin || "").replace(/[\s-]+/g, "");
        payload.government_id_type = values.government_id_type || "nin_slip";
        payload.cac_number = (values.cac_number || "").replace(/[\s-]+/g, "").toUpperCase();
        payload.cac_business_name = values.cac_business_name || "";
        payload.guarantor_name = values.guarantor_name || "";
        payload.guarantor_phone = values.guarantor_phone || "";
        payload.bank_name = values.bank_name || "";
        payload.bank_account_number = (values.bank_account_number || "").replace(/[\s-]+/g, "");
        payload.bank_account_name = values.bank_account_name || "";
      }

      const res = await apiRequest<{ user: User }>("/auth/register/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify(payload),
      });
      await refreshUser();

      if (accountType === "customer") {
        const u = res.user;
        const params = new URLSearchParams();
        if (u.state) params.set("state", u.state);
        if (u.lga) params.set("lga", u.lga);
        if (u.ward) params.set("ward", u.ward);
        if (u.polling_unit) params.set("polling_unit", u.polling_unit);
        router.push(`/marketplace${params.toString() ? `?${params.toString()}` : ""}`);
      } else {
        // Send new artisans straight to KYC Verification to upload NIN slip / CAC / address proof
        router.push("/verification");
      }
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Registration failed.");
    }
  }

  return (
    <div className="mezer-hero-bg relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-4 py-10">
      <div
        aria-hidden="true"
        className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[460px] w-[460px] rounded-full"
      />
      <div className="relative mb-6 flex w-full max-w-2xl items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-soft hover:text-brand-700"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to ArtisanOS
        </Link>
        <Link
          href="/marketplace"
          className="text-xs font-semibold text-brand-700 hover:underline"
        >
          Browse Nearby Artisans
        </Link>
      </div>
      <Card className="relative w-full max-w-2xl rounded-mezer-lg">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto mb-1 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Wrench className="h-5 w-5" />
          </div>
          <div className="mezer-eyebrow justify-center">ArtisanOS Nigeria · All 774 LGAs</div>
          <h1 className="text-2xl font-extrabold tracking-tight text-plum">
            {accountType === "artisan"
              ? "Register your craft & pin your location"
              : "Create your account & discover artisans near you"}
          </h1>
          <p className="text-sm text-ink-soft">
            Auto-detect or select your neighborhood so nearby artisans immediately appear for your
            area.
          </p>

          {/* Role Toggle: Artisan vs Customer */}
          <div className="mx-auto mt-2 grid w-full max-w-md grid-cols-2 gap-1 rounded-2xl border border-line bg-surface p-1 sm:inline-flex sm:w-auto sm:max-w-none sm:rounded-full">
            <button
              type="button"
              onClick={() => setAccountType("artisan")}
              className={`inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold transition-colors sm:rounded-full sm:px-4 sm:py-1.5 ${
                accountType === "artisan"
                  ? "bg-plum text-white shadow-sm"
                  : "text-ink-soft hover:text-plum"
              }`}
            >
              <Store className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Artisan / Business</span>
            </button>
            <button
              type="button"
              onClick={() => setAccountType("customer")}
              className={`inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold transition-colors sm:rounded-full sm:px-4 sm:py-1.5 ${
                accountType === "customer"
                  ? "bg-plum text-white shadow-sm"
                  : "text-ink-soft hover:text-plum"
              }`}
            >
              <UserCheck className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">Customer / Patron</span>
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {serverError && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {serverError}
              </div>
            )}

            {/* Hyper-Local Nigerian Ward & Polling Unit Detection (First!) */}
            <div className="space-y-3 rounded-mezer-sm border border-brand-200 bg-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-xs font-extrabold uppercase tracking-wider text-plum">
                  <MapPin className="h-3.5 w-3.5 text-brand-700" />
                  Your Location
                </span>
                <span className="text-[11px] font-semibold text-brand-700">
                  All 36 States, FCT &amp; 774 LGAs · Auto-detect supported
                </span>
              </div>
              <NigeriaLocationPicker
                value={location}
                onChange={setLocation}
                onDetectedMeta={handleDetectedMeta}
                autoDetectOnMount
                allowCreateNew
                idPrefix="reg-loc"
              />
              <div>
                <Label htmlFor="reg-landmark">Nearest street / junction / landmark</Label>
                <Input
                  id="reg-landmark"
                  className="bg-white"
                  placeholder="e.g. Beside Allen Roundabout Plaza, Ikeja"
                  {...register("landmark")}
                />
              </div>

              {/* Instant Preview of Related Artisans Springing Up Nearby */}
              {hasLocation && nearbyPreview && nearbyPreview.length > 0 && (
                <div className="rounded-xl border border-emerald-200 bg-white p-3">
                  <div className="mb-2 flex items-center justify-between text-xs font-bold text-emerald-800">
                    <span className="inline-flex items-center gap-1.5">
                      <Navigation className="h-3.5 w-3.5" />
                      {nearbyPreview.length} related{" "}
                      {nearbyPreview.length === 1 ? "artisan" : "artisans"} already active near your
                      area!
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    {nearbyPreview.slice(0, 3).map((art) => (
                      <div
                        key={art.slug}
                        className="flex items-center justify-between rounded-lg bg-surface px-2.5 py-1.5 text-xs"
                      >
                        <div className="min-w-0">
                          <span className="font-bold text-plum">{art.organization_name}</span>
                          <span className="ml-1.5 text-ink-soft">· {art.category_label}</span>
                        </div>
                        <span className="inline-flex shrink-0 items-center gap-1 text-[10px] font-bold text-brand-700">
                          {art.proximity_label || art.ward_name || art.lga_name}
                          {art.phone && <Phone className="h-3 w-3 text-emerald-600" />}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="reg-name">Your full name</Label>
                <Input id="reg-name" placeholder="Adaobi Nwosu" {...register("full_name")} />
                {errors.full_name && (
                  <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="reg-phone">Phone / WhatsApp</Label>
                <Input id="reg-phone" placeholder="+2348012345678" {...register("phone")} />
                {errors.phone && (
                  <p className="mt-1 text-xs text-red-600">{errors.phone.message}</p>
                )}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="reg-email">Email</Label>
                <Input
                  id="reg-email"
                  type="email"
                  placeholder="ada@atelier.ng"
                  {...register("email")}
                />
                {errors.email && (
                  <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="reg-password">Password</Label>
                <Input id="reg-password" type="password" {...register("password")} />
                {errors.password && (
                  <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                )}
              </div>
            </div>

            {accountType === "artisan" && (
              <>
                <hr className="border-line-soft" />
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="reg-org-name">Business / workshop name</Label>
                    <Input
                      id="reg-org-name"
                      placeholder="e.g. VoltCraft Solar & Electricals"
                      {...register("organization_name")}
                    />
                  </div>
                  <div>
                    <Label htmlFor="reg-category">Primary trade / craft</Label>
                    <Select id="reg-category" {...register("organization_category")}>
                      {ARTISAN_CATEGORIES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <Label htmlFor="reg-callout">Call-out fee (NGN, optional)</Label>
                    <Input
                      id="reg-callout"
                      type="number"
                      min="0"
                      placeholder="e.g. 4000"
                      {...register("callout_fee")}
                    />
                  </div>
                  <div>
                    <Label htmlFor="reg-currency">Currency</Label>
                    <Input id="reg-currency" maxLength={3} {...register("currency")} />
                    {errors.currency && (
                      <p className="mt-1 text-xs text-red-600">{errors.currency.message}</p>
                    )}
                  </div>
                  <div>
                    <Label htmlFor="reg-unit">Measurement unit</Label>
                    <Select id="reg-unit" {...register("preferred_unit")}>
                      <option value="cm">Centimetres (cm)</option>
                      <option value="in">Inches (in)</option>
                    </Select>
                  </div>
                </div>

                <div>
                  <Label htmlFor="reg-skills">Key skills / services (comma-separated)</Label>
                  <Input
                    id="reg-skills"
                    placeholder="e.g. House Wiring, Solar Inverter, DB Panel Repair"
                    {...register("skills_text")}
                  />
                </div>

                <label className="flex items-center gap-2 text-sm font-semibold text-plum">
                  <input
                    type="checkbox"
                    className="accent-brand-700"
                    {...register("available_for_callout")}
                  />
                  Available for on-site / home call-out work in my neighborhood &amp; nearby areas
                </label>

                {/* Strict Anti-Scam KYC Verification Block */}
                <div className="space-y-3 rounded-mezer-sm border border-emerald-200 bg-emerald-50/50 p-4">
                  <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-emerald-900">
                    <ShieldCheck className="h-4 w-4 text-emerald-700" />
                    Strict Artisan Identity Verification (Anti-Scam KYC)
                  </div>
                  <p className="text-xs leading-relaxed text-emerald-900/80">
                    To protect customers from scammers, every artisan must provide a valid 11-digit
                    Nigerian NIN. After signup, upload your NIN slip, CAC certificate (if
                    registered), and proof of workshop address to unlock your live Verified badge
                    and Escrow payouts.
                  </p>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="reg-nin">11-digit Nigerian NIN (Required)</Label>
                      <Input
                        id="reg-nin"
                        className="bg-white"
                        maxLength={14}
                        placeholder="e.g. 12345678901"
                        {...register("nin")}
                      />
                    </div>
                    <div>
                      <Label htmlFor="reg-id-type">Government ID type</Label>
                      <Select id="reg-id-type" className="bg-white" {...register("government_id_type")}>
                        <option value="nin_slip">NIN Slip / National ID</option>
                        <option value="voters_card">Permanent Voter&apos;s Card (PVC)</option>
                        <option value="drivers_license">Nigerian Driver&apos;s License</option>
                        <option value="intl_passport">Nigerian International Passport</option>
                      </Select>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="reg-cac">CAC Number (RC / BN / IT, optional)</Label>
                      <Input
                        id="reg-cac"
                        className="bg-white"
                        placeholder="e.g. BN2345678 or RC1234567"
                        {...register("cac_number")}
                      />
                    </div>
                    <div>
                      <Label htmlFor="reg-cac-name">CAC Registered Business Name</Label>
                      <Input
                        id="reg-cac-name"
                        className="bg-white"
                        placeholder="Registered CAC name (optional)"
                        {...register("cac_business_name")}
                      />
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="reg-guar-name">Guarantor full name</Label>
                      <Input
                        id="reg-guar-name"
                        className="bg-white"
                        placeholder="Trusted community / guild guarantor"
                        {...register("guarantor_name")}
                      />
                    </div>
                    <div>
                      <Label htmlFor="reg-guar-phone">Guarantor phone</Label>
                      <Input
                        id="reg-guar-phone"
                        className="bg-white"
                        placeholder="+23480..."
                        {...register("guarantor_phone")}
                      />
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <div>
                      <Label htmlFor="reg-bank-name">Escrow payout bank</Label>
                      <Input
                        id="reg-bank-name"
                        className="bg-white"
                        placeholder="e.g. GTBank, Zenith"
                        {...register("bank_name")}
                      />
                    </div>
                    <div>
                      <Label htmlFor="reg-bank-acct">10-digit NUBAN</Label>
                      <Input
                        id="reg-bank-acct"
                        className="bg-white"
                        maxLength={10}
                        placeholder="0123456789"
                        {...register("bank_account_number")}
                      />
                    </div>
                    <div>
                      <Label htmlFor="reg-bank-acct-name">Account name</Label>
                      <Input
                        id="reg-bank-acct-name"
                        className="bg-white"
                        placeholder="Matches NIN / CAC"
                        {...register("bank_account_name")}
                      />
                    </div>
                  </div>
                </div>
              </>
            )}

            <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
              {isSubmitting
                ? "Validating KYC & creating account..."
                : accountType === "artisan"
                  ? "Submit KYC & create artisan workspace"
                  : "Sign up & show nearby artisans"}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-soft">
            Already have an account?{" "}
            <Link href="/login" className="font-semibold text-brand-700 hover:underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
