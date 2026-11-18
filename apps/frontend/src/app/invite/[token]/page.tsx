"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Scissors } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { PublicInvitationDetail } from "@/types/api";

export default function AcceptInvitationPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const router = useRouter();
  const { user, refreshUser, switchOrganization } = useAuth();

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const { data: invite, isLoading, error } = useQuery({
    queryKey: ["public-invitation", token],
    queryFn: () =>
      apiRequest<PublicInvitationDetail>(`/public/invitations/${token}/`, {
        skipOrgHeader: true,
      }),
    enabled: !!token,
    retry: false,
  });

  const matchingSignedInUser =
    !!user && !!invite && user.email.toLowerCase() === invite.email.toLowerCase();

  const acceptMutation = useMutation({
    mutationFn: () =>
      apiRequest<{ organization_id: string }>(`/public/invitations/${token}/accept/`, {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify(
          matchingSignedInUser
            ? {}
            : {
                full_name: fullName,
                phone,
                password,
              }
        ),
      }),
    onSuccess: async (res) => {
      await refreshUser();
      switchOrganization(res.organization_id);
      router.push("/dashboard");
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : "Could not accept invitation.");
    },
  });

  return (
    <div className="mezer-hero-bg relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-4">
      <div
        aria-hidden="true"
        className="mezer-hero-glow pointer-events-none absolute -right-24 -top-24 h-[460px] w-[460px] rounded-full"
      />
      <div className="relative mb-6 flex items-center gap-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
          <Scissors className="h-5 w-5" />
        </div>
        <span className="text-lg font-extrabold tracking-tight text-plum">ArtisanOS</span>
      </div>

      {isLoading && <Card className="h-44 w-full max-w-md animate-pulse bg-white/70" />}

      {error && (
        <Card className="relative w-full max-w-md rounded-mezer-lg">
          <CardContent className="py-10 text-center">
            <div className="mezer-eyebrow justify-center">Invitation Unavailable</div>
            <h1 className="mt-2 text-xl font-extrabold text-plum">Cannot use this invite link</h1>
            <p className="mt-1.5 text-sm text-ink-soft">
              {error instanceof Error ? error.message : "This invitation has expired or been revoked."}
            </p>
          </CardContent>
        </Card>
      )}

      {invite && (
        <Card className="relative w-full max-w-md rounded-mezer-lg">
          <CardHeader className="text-center">
            <div className="mezer-eyebrow justify-center">Workspace Invitation</div>
            <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-plum">
              Join {invite.organization_name}
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Invited as{" "}
              <span className="font-semibold capitalize text-brand-700">
                {invite.role.replace("_", " ")}
              </span>{" "}
              for <span className="font-semibold text-ink">{invite.email}</span>
            </p>
            <p className="mt-1 text-xs text-ink-faint">
              Expires {formatDateTime(invite.expires_at)}
            </p>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault();
                acceptMutation.mutate();
              }}
            >
              {errorMsg && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {errorMsg}
                </div>
              )}

              {matchingSignedInUser ? (
                <div className="rounded-mezer-sm border border-emerald-200 bg-emerald-50 p-4 text-center text-sm text-emerald-900">
                  <CheckCircle2 className="mx-auto mb-1.5 h-6 w-6 text-emerald-600" />
                  Signed in as <strong>{user.email}</strong>. Click below to join immediately.
                </div>
              ) : (
                <>
                  {!invite.account_exists && (
                    <>
                      <div>
                        <Label htmlFor="inv-name">Your full name</Label>
                        <Input
                          id="inv-name"
                          required
                          placeholder="Emeka Tailor"
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                        />
                      </div>
                      <div>
                        <Label htmlFor="inv-phone">Phone (optional)</Label>
                        <Input
                          id="inv-phone"
                          placeholder="+2348012345678"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                        />
                      </div>
                    </>
                  )}
                  <div>
                    <Label htmlFor="inv-password">
                      {invite.account_exists
                        ? "Enter your existing ArtisanOS password"
                        : "Create a password (min 8 characters)"}
                    </Label>
                    <Input
                      id="inv-password"
                      type="password"
                      required
                      minLength={8}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </>
              )}

              <Button type="submit" size="lg" className="w-full" disabled={acceptMutation.isPending}>
                {acceptMutation.isPending ? "Joining workspace..." : "Accept & enter workspace"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
