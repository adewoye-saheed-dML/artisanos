"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCopy, MailPlus, Shield, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  MembershipRole,
  Organization,
  OrganizationInvitation,
  OrganizationMember,
} from "@/types/api";

export default function SettingsPage() {
  const { user, activeOrganization, activeMembership, refreshUser, switchOrganization } = useAuth();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("NGN");
  const [preferredUnit, setPreferredUnit] = useState<"cm" | "in">("cm");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");

  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgCategory, setNewOrgCategory] = useState("tailor");
  const [newOrgError, setNewOrgError] = useState("");

  // Team invitation state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<MembershipRole>("artisan");
  const [generatedInviteLink, setGeneratedInviteLink] = useState("");
  const [teamError, setTeamError] = useState("");

  useEffect(() => {
    if (activeOrganization) {
      setName(activeOrganization.name);
      setPhone(activeOrganization.phone);
      setEmail(activeOrganization.email);
      setAddress(activeOrganization.address);
      setCity(activeOrganization.city);
      setCountry(activeOrganization.country);
      setCurrency(activeOrganization.currency);
      setPreferredUnit(activeOrganization.preferred_unit);
    }
  }, [activeOrganization]);

  const isOwner = activeMembership?.role === "owner";
  const canEdit = activeMembership?.role === "owner" || activeMembership?.role === "manager";

  const { data: members } = useQuery({
    queryKey: ["org-members", activeOrganization?.id],
    queryFn: () =>
      apiRequest<OrganizationMember[]>(`/organizations/${activeOrganization?.id}/members/`),
    enabled: !!activeOrganization?.id,
  });

  const { data: invitations } = useQuery({
    queryKey: ["org-invitations", activeOrganization?.id],
    queryFn: () =>
      apiRequest<OrganizationInvitation[]>(`/organizations/${activeOrganization?.id}/invitations/`),
    enabled: !!activeOrganization?.id && canEdit,
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      apiRequest<Organization>(`/organizations/${activeOrganization?.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          name,
          phone,
          email,
          address,
          city,
          country,
          currency: currency.toUpperCase(),
          preferred_unit: preferredUnit,
        }),
      }),
    onSuccess: async () => {
      setSaveError("");
      setSaveMessage("Workspace settings saved.");
      await refreshUser();
    },
    onError: (err) => {
      setSaveMessage("");
      setSaveError(err instanceof Error ? err.message : "Failed to save settings.");
    },
  });

  const createOrgMutation = useMutation({
    mutationFn: () =>
      apiRequest<Organization>("/organizations/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          name: newOrgName,
          category: newOrgCategory,
          currency: "NGN",
          preferred_unit: "cm",
        }),
      }),
    onSuccess: async (org) => {
      setNewOrgName("");
      setNewOrgError("");
      await refreshUser();
      switchOrganization(org.id);
    },
    onError: (err) => {
      setNewOrgError(err instanceof Error ? err.message : "Failed to create workspace.");
    },
  });

  const inviteMutation = useMutation({
    mutationFn: () =>
      apiRequest<OrganizationInvitation>(`/organizations/${activeOrganization?.id}/invitations/`, {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail,
          role: inviteRole,
        }),
      }),
    onSuccess: (inv) => {
      queryClient.invalidateQueries({ queryKey: ["org-invitations", activeOrganization?.id] });
      setInviteEmail("");
      setTeamError("");
      if (inv.invite_path && typeof window !== "undefined") {
        setGeneratedInviteLink(`${window.location.origin}${inv.invite_path}`);
      }
    },
    onError: (err) => {
      setTeamError(err instanceof Error ? err.message : "Could not send invitation.");
    },
  });

  const revokeInviteMutation = useMutation({
    mutationFn: (inviteId: string) =>
      apiRequest(`/organizations/${activeOrganization?.id}/invitations/${inviteId}/revoke/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-invitations", activeOrganization?.id] });
    },
    onError: (err) => {
      setTeamError(err instanceof Error ? err.message : "Could not revoke invitation.");
    },
  });

  const updateMemberMutation = useMutation({
    mutationFn: ({
      memberId,
      payload,
    }: {
      memberId: string;
      payload: { role?: MembershipRole; status?: "active" | "suspended" };
    }) =>
      apiRequest<OrganizationMember>(
        `/organizations/${activeOrganization?.id}/members/${memberId}/`,
        {
          method: "PATCH",
          body: JSON.stringify(payload),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-members", activeOrganization?.id] });
      setTeamError("");
    },
    onError: (err) => {
      setTeamError(err instanceof Error ? err.message : "Could not update team member.");
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <div className="mezer-eyebrow">Organization Configuration</div>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
            Workspace &amp; Team Settings
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            Configure your organization profile, invite artisans, manage roles, or launch another workspace.
          </p>
        </div>

        {/* Team & Invitations */}
        <Card className="overflow-hidden">
          <CardHeader className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                <Users className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-base font-bold text-plum">Team Members &amp; Roles</h2>
                <p className="text-xs text-ink-faint">
                  Invite tailors, managers, and sales assistants with role-based access control.
                </p>
              </div>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-surface-blush px-3 py-1 text-xs font-semibold text-brand-700">
              <Shield className="h-3.5 w-3.5" /> Your role: {activeMembership?.role}
            </span>
          </CardHeader>
          <CardContent className="space-y-6">
            {teamError && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                {teamError}
              </div>
            )}

            {canEdit && (
              <form
                className="grid gap-3 rounded-mezer-sm border border-line bg-surface-blush p-4 sm:grid-cols-[1.4fr_0.9fr_auto]"
                onSubmit={(e) => {
                  e.preventDefault();
                  inviteMutation.mutate();
                }}
              >
                <div>
                  <Label htmlFor="invite-email">Invite by email</Label>
                  <Input
                    id="invite-email"
                    type="email"
                    required
                    className="bg-white"
                    placeholder="tailor@workshop.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="invite-role">Role</Label>
                  <Select
                    id="invite-role"
                    className="bg-white"
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as MembershipRole)}
                  >
                    {isOwner && <option value="manager">Manager</option>}
                    <option value="artisan">Artisan / Tailor</option>
                    <option value="sales_assistant">Sales Assistant</option>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button type="submit" disabled={inviteMutation.isPending} className="w-full sm:w-auto">
                    <MailPlus className="h-4 w-4" />
                    {inviteMutation.isPending ? "Creating..." : "Create invite link"}
                  </Button>
                </div>
              </form>
            )}

            {generatedInviteLink && (
              <div className="flex flex-col gap-3 rounded-mezer-sm bg-plum p-4 text-white sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="mezer-eyebrow-light">Secure Team Invite Link (7-day expiry)</div>
                  <div className="mt-1 truncate font-mono text-xs text-white/90">
                    {generatedInviteLink}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="light"
                  onClick={() => navigator.clipboard?.writeText(generatedInviteLink)}
                >
                  <ClipboardCopy className="h-4 w-4" />
                  Copy link
                </Button>
              </div>
            )}

            {/* Active & Suspended Members Table */}
            <div className="overflow-x-auto rounded-mezer-sm border border-line">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line bg-surface-blush text-[11px] font-bold uppercase tracking-wider text-ink-faint">
                  <tr>
                    <th className="px-4 py-3">Member</th>
                    <th className="px-4 py-3">Role</th>
                    <th className="px-4 py-3">Status</th>
                    {canEdit && <th className="px-4 py-3 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-soft bg-white">
                  {members?.map((m) => {
                    const isSelf = m.user_id === user?.id;
                    const canManageTarget =
                      canEdit &&
                      !isSelf &&
                      (isOwner || (m.role !== "owner" && m.role !== "manager"));
                    return (
                      <tr key={m.id}>
                        <td className="px-4 py-3.5">
                          <div className="font-semibold text-plum">
                            {m.full_name} {isSelf && <span className="text-xs text-ink-faint">(You)</span>}
                          </div>
                          <div className="text-xs text-ink-faint">{m.email}</div>
                        </td>
                        <td className="px-4 py-3.5">
                          {canManageTarget ? (
                            <Select
                              aria-label={`Role for ${m.full_name}`}
                              value={m.role}
                              className="mt-0 max-w-[170px] py-1.5 text-xs"
                              onChange={(e) =>
                                updateMemberMutation.mutate({
                                  memberId: m.id,
                                  payload: { role: e.target.value as MembershipRole },
                                })
                              }
                            >
                              {isOwner && <option value="owner">Owner</option>}
                              {isOwner && <option value="manager">Manager</option>}
                              <option value="artisan">Artisan</option>
                              <option value="sales_assistant">Sales Assistant</option>
                            </Select>
                          ) : (
                            <span className="capitalize font-medium text-ink">{m.role.replace("_", " ")}</span>
                          )}
                        </td>
                        <td className="px-4 py-3.5">
                          <StatusBadge status={m.status} />
                        </td>
                        {canEdit && (
                          <td className="px-4 py-3.5 text-right">
                            {canManageTarget && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  updateMemberMutation.mutate({
                                    memberId: m.id,
                                    payload: {
                                      status: m.status === "active" ? "suspended" : "active",
                                    },
                                  })
                                }
                              >
                                {m.status === "active" ? "Suspend" : "Reactivate"}
                              </Button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Invitations history */}
            {canEdit && invitations && invitations.length > 0 && (
              <div>
                <h3 className="mb-2.5 text-xs font-extrabold uppercase tracking-wider text-ink-faint">
                  Recent Invitations
                </h3>
                <div className="divide-y divide-line-soft rounded-mezer-sm border border-line bg-white">
                  {invitations.map((inv) => (
                    <div
                      key={inv.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
                    >
                      <div>
                        <div className="text-sm font-semibold text-plum">{inv.email}</div>
                        <div className="text-xs text-ink-faint">
                          Role: <span className="capitalize">{inv.role.replace("_", " ")}</span> ·
                          Expires {formatDateTime(inv.expires_at)}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={inv.status} />
                        {inv.status === "pending" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => revokeInviteMutation.mutate(inv.id)}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Organization Profile & Create New Workspace */}
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <h2 className="text-base font-bold text-plum">Organization Profile</h2>
            </CardHeader>
            <CardContent className="space-y-4">
              {saveMessage && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-800">
                  {saveMessage}
                </div>
              )}
              {saveError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {saveError}
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="org-name">Workspace name</Label>
                  <Input id="org-name" value={name} onChange={(e) => setName(e.target.value)} disabled={!canEdit} />
                </div>
                <div>
                  <Label htmlFor="org-email">Business email</Label>
                  <Input id="org-email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={!canEdit} />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <Label htmlFor="org-phone">Phone</Label>
                  <Input id="org-phone" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={!canEdit} />
                </div>
                <div>
                  <Label htmlFor="org-currency">Currency</Label>
                  <Input
                    id="org-currency"
                    maxLength={3}
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                    disabled={!canEdit}
                  />
                </div>
                <div>
                  <Label htmlFor="org-unit">Default unit</Label>
                  <Select
                    id="org-unit"
                    value={preferredUnit}
                    onChange={(e) => setPreferredUnit(e.target.value as "cm" | "in")}
                    disabled={!canEdit}
                  >
                    <option value="cm">Centimetres (cm)</option>
                    <option value="in">Inches (in)</option>
                  </Select>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="org-city">City</Label>
                  <Input id="org-city" value={city} onChange={(e) => setCity(e.target.value)} disabled={!canEdit} />
                </div>
                <div>
                  <Label htmlFor="org-country">Country</Label>
                  <Input id="org-country" value={country} onChange={(e) => setCountry(e.target.value)} disabled={!canEdit} />
                </div>
              </div>

              <div>
                <Label htmlFor="org-address">Address</Label>
                <Textarea id="org-address" rows={2} value={address} onChange={(e) => setAddress(e.target.value)} disabled={!canEdit} />
              </div>

              {canEdit && (
                <div className="flex justify-end">
                  <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
                    {updateMutation.isPending ? "Saving..." : "Save changes"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">Add Another Workspace</h2>
            </CardHeader>
            <CardContent className="space-y-4">
              {newOrgError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {newOrgError}
                </div>
              )}
              <div>
                <Label htmlFor="new-org-name">Workspace name</Label>
                <Input
                  id="new-org-name"
                  placeholder="e.g. Abuja Leather Studio"
                  value={newOrgName}
                  onChange={(e) => setNewOrgName(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="new-org-cat">Category</Label>
                <Select
                  id="new-org-cat"
                  value={newOrgCategory}
                  onChange={(e) => setNewOrgCategory(e.target.value)}
                >
                  <option value="tailor">Tailor</option>
                  <option value="shoemaker">Shoemaker</option>
                  <option value="leatherworker">Leatherworker</option>
                  <option value="other">Other</option>
                </Select>
              </div>
              <Button
                className="w-full"
                onClick={() => createOrgMutation.mutate()}
                disabled={createOrgMutation.isPending || newOrgName.trim().length < 2}
              >
                {createOrgMutation.isPending ? "Creating..." : "Create & switch"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
