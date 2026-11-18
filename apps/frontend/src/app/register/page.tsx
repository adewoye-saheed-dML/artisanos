"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Scissors } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";

const registerSchema = z.object({
  full_name: z.string().min(2, "Full name is required."),
  email: z.string().email("Enter a valid email address."),
  phone: z.string().optional(),
  password: z.string().min(8, "Password must be at least 8 characters."),
  organization_name: z.string().min(2, "Business/workspace name is required."),
  organization_category: z.enum(["tailor", "shoemaker", "leatherworker", "other"]),
  currency: z.string().length(3, "Use a 3-letter currency code (e.g. NGN, USD)."),
  preferred_unit: z.enum(["cm", "in"]),
  city: z.string().optional(),
  country: z.string().optional(),
});

type RegisterValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [serverError, setServerError] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      organization_category: "tailor",
      currency: "NGN",
      preferred_unit: "cm",
    },
  });

  useEffect(() => {
    if (user) {
      router.replace("/dashboard");
    }
  }, [user, router]);

  async function onSubmit(values: RegisterValues) {
    setServerError("");
    try {
      await apiRequest("/auth/register/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          ...values,
          currency: values.currency.toUpperCase(),
        }),
      });
      await refreshUser();
      router.push("/dashboard");
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
      <div className="relative mb-6 flex w-full max-w-lg items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-soft hover:text-brand-700"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to ArtisanOS
        </Link>
      </div>
      <Card className="relative w-full max-w-lg rounded-mezer-lg">
        <CardHeader className="space-y-1.5 text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Scissors className="h-5 w-5" />
          </div>
          <div className="mezer-eyebrow justify-center">Workspace Onboarding</div>
          <h1 className="text-2xl font-extrabold tracking-tight text-plum">
            Create your ArtisanOS workspace
          </h1>
          <p className="text-sm text-ink-soft">
            Set up your owner account and isolated business workspace in one step.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {serverError && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {serverError}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="reg-name">Your full name</Label>
                <Input id="reg-name" placeholder="Adaobi Nwosu" {...register("full_name")} />
                {errors.full_name && (
                  <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="reg-phone">Phone (optional)</Label>
                <Input id="reg-phone" placeholder="+2348012345678" {...register("phone")} />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="reg-email">Email</Label>
                <Input id="reg-email" type="email" placeholder="ada@atelier.ng" {...register("email")} />
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

            <hr className="border-line-soft" />

            <div>
              <Label htmlFor="reg-org-name">Business / workspace name</Label>
              <Input
                id="reg-org-name"
                placeholder="e.g. Lagos Bespoke Tailoring"
                {...register("organization_name")}
              />
              {errors.organization_name && (
                <p className="mt-1 text-xs text-red-600">{errors.organization_name.message}</p>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <Label htmlFor="reg-category">Category</Label>
                <Select id="reg-category" {...register("organization_category")}>
                  <option value="tailor">Tailor</option>
                  <option value="shoemaker">Shoemaker</option>
                  <option value="leatherworker">Leatherworker</option>
                  <option value="other">Other</option>
                </Select>
              </div>
              <div>
                <Label htmlFor="reg-currency">Currency</Label>
                <Input id="reg-currency" maxLength={3} {...register("currency")} />
                {errors.currency && (
                  <p className="mt-1 text-xs text-red-600">{errors.currency.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="reg-unit">Preferred unit</Label>
                <Select id="reg-unit" {...register("preferred_unit")}>
                  <option value="cm">Centimetres (cm)</option>
                  <option value="in">Inches (in)</option>
                </Select>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="reg-city">City (optional)</Label>
                <Input id="reg-city" placeholder="Lagos" {...register("city")} />
              </div>
              <div>
                <Label htmlFor="reg-country">Country (optional)</Label>
                <Input id="reg-country" placeholder="Nigeria" {...register("country")} />
              </div>
            </div>

            <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Creating account & workspace..." : "Create workspace"}
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
