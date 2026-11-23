"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Wrench } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Password is required."),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [serverError, setServerError] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
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

  async function onSubmit(values: LoginValues) {
    setServerError("");
    try {
      const res = await apiRequest<{ user: { memberships: unknown[]; state?: string | null; lga?: string | null; ward?: string | null; polling_unit?: string | null } }>("/auth/login/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify(values),
      });
      await refreshUser();
      if (res.user.memberships.length > 0) {
        router.push("/dashboard");
      } else {
        const params = new URLSearchParams();
        if (res.user.state) params.set("state", res.user.state);
        if (res.user.lga) params.set("lga", res.user.lga);
        if (res.user.ward) params.set("ward", res.user.ward);
        if (res.user.polling_unit) params.set("polling_unit", res.user.polling_unit);
        router.push(`/marketplace${params.toString() ? `?${params.toString()}` : ""}`);
      }
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "Failed to sign in.");
    }
  }

  return (
    <div className="mezer-hero-bg relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-4">
      <div
        aria-hidden="true"
        className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[460px] w-[460px] rounded-full"
      />
      <div className="relative mb-6 flex w-full max-w-md items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-soft hover:text-brand-700"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to ArtisanOS
        </Link>
      </div>
      <Card className="relative w-full max-w-md rounded-mezer-lg">
        <CardHeader className="space-y-1.5 text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Wrench className="h-5 w-5" />
          </div>
          <div className="mezer-eyebrow justify-center">Artisan Workspace Access</div>
          <h1 className="text-2xl font-extrabold tracking-tight text-plum">Sign in to ArtisanOS</h1>
          <p className="text-sm text-ink-soft">
            Manage your storefront, work call-outs, customers, and orders.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {serverError && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {serverError}
              </div>
            )}
            <div>
              <Label htmlFor="login-email">Email</Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="email"
                placeholder="you@atelier.com"
                {...register("email")}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                {...register("password")}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Signing in..." : "Sign in"}
            </Button>
          </form>
          <p className="mt-5 text-center text-sm text-ink-soft">
            New artisan business?{" "}
            <Link href="/register" className="font-semibold text-brand-700 hover:underline">
              Create your workspace
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
