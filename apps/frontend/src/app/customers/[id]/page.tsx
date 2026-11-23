"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  ClipboardCopy,
  Download,
  Edit3,
  History,
  Link2,
  Plus,
  RotateCcw,
  Ruler,
  Share2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { CustomerReferencePhotosSection } from "@/components/measurements/customer-reference-photos";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatCurrency, formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  Appointment,
  Customer,
  MeasurementProfile,
  MeasurementRequestItem,
  MeasurementShareLink,
  MeasurementTemplate,
  Order,
  PaginatedResponse,
  UnitSystem,
} from "@/types/api";

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const customerId = params.id;
  const { activeOrganization, activeMembership } = useAuth();
  const queryClient = useQueryClient();

  const canArchive = activeMembership?.role === "owner" || activeMembership?.role === "manager";

  // Inline customer edit state
  const [editingCustomer, setEditingCustomer] = useState(false);
  const [editFullName, setEditFullName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editAddress, setEditAddress] = useState("");
  const [editContact, setEditContact] = useState<"phone" | "whatsapp" | "email" | "sms">("whatsapp");
  const [editNotes, setEditNotes] = useState("");
  const [customerEditError, setCustomerEditError] = useState("");

  // Measurement form state
  const [showRecordForm, setShowRecordForm] = useState(false);
  const [editingProfile, setEditingProfile] = useState<MeasurementProfile | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [label, setLabel] = useState("Primary Measurements");
  const [unitSystem, setUnitSystem] = useState<UnitSystem>(
    activeOrganization?.preferred_unit || "cm"
  );
  const [notes, setNotes] = useState("");
  const [fieldInputs, setFieldInputs] = useState<Record<string, string>>({});
  const [measureError, setMeasureError] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);

  const [generatedLink, setGeneratedLink] = useState("");
  const [requestError, setRequestError] = useState("");

  // Fit Passport sharing & portability import state
  const [showSharePanel, setShowSharePanel] = useState(false);
  const [shareRecipient, setShareRecipient] = useState("");
  const [shareConsent, setShareConsent] = useState(false);
  const [generatedShareLink, setGeneratedShareLink] = useState("");
  const [shareError, setShareError] = useState("");
  const [showImportPanel, setShowImportPanel] = useState(false);
  const [importToken, setImportToken] = useState("");
  const [importError, setImportError] = useState("");

  const { data: customer, isLoading: loadingCustomer } = useQuery({
    queryKey: ["customer", activeOrganization?.id, customerId],
    queryFn: () => apiRequest<Customer>(`/customers/${customerId}/`),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const { data: templatesData } = useQuery({
    queryKey: ["measurement-templates", activeOrganization?.id],
    queryFn: () => apiRequest<PaginatedResponse<MeasurementTemplate>>("/measurement-templates/"),
    enabled: !!activeOrganization?.id,
  });

  const { data: profilesData, isLoading: loadingProfiles } = useQuery({
    queryKey: ["customer-measurements", activeOrganization?.id, customerId],
    queryFn: () =>
      apiRequest<PaginatedResponse<MeasurementProfile>>(`/customers/${customerId}/measurements/`),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const { data: ordersData } = useQuery({
    queryKey: ["customer-orders", activeOrganization?.id, customerId],
    queryFn: () => apiRequest<PaginatedResponse<Order>>(`/orders/?customer=${customerId}`),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const { data: appointmentsData } = useQuery({
    queryKey: ["customer-appointments", activeOrganization?.id, customerId],
    queryFn: () =>
      apiRequest<PaginatedResponse<Appointment>>(`/appointments/?customer=${customerId}`),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const { data: requestsData } = useQuery({
    queryKey: ["customer-measurement-requests", activeOrganization?.id, customerId],
    queryFn: () =>
      apiRequest<PaginatedResponse<MeasurementRequestItem>>(
        `/measurement-requests/?customer=${customerId}`
      ),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const { data: sharesData } = useQuery({
    queryKey: ["customer-measurement-shares", activeOrganization?.id, customerId],
    queryFn: () =>
      apiRequest<PaginatedResponse<MeasurementShareLink>>(
        `/measurement-shares/?customer=${customerId}`
      ),
    enabled: !!activeOrganization?.id && !!customerId,
  });

  const templates = useMemo(() => templatesData?.results || [], [templatesData]);
  const activeTemplate = useMemo(() => {
    if (editingProfile) {
      return (
        templates.find((t) => t.latest_version?.id === editingProfile.template_version) ||
        templates.find((t) => t.name === editingProfile.template_name) ||
        templates[0]
      );
    }
    if (selectedTemplateId) {
      return templates.find((t) => t.id === selectedTemplateId) || templates[0];
    }
    return templates.find((t) => t.slug === "standard-tailoring") || templates[0];
  }, [templates, selectedTemplateId, editingProfile]);

  const activeFields = useMemo(
    () => activeTemplate?.latest_version?.fields || [],
    [activeTemplate]
  );

  const profiles = useMemo(() => profilesData?.results || [], [profilesData]);
  const displayedProfile =
    profiles.find((p) => p.id === selectedProfileId) ||
    profiles.find((p) => p.is_latest) ||
    profiles[0] ||
    null;

  function openCustomerEdit() {
    if (!customer) return;
    setEditFullName(customer.full_name);
    setEditPhone(customer.phone);
    setEditEmail(customer.email);
    setEditAddress(customer.address);
    setEditContact(customer.preferred_contact_method);
    setEditNotes(customer.notes);
    setCustomerEditError("");
    setEditingCustomer(true);
  }

  const updateCustomerMutation = useMutation({
    mutationFn: () =>
      apiRequest<Customer>(`/customers/${customerId}/`, {
        method: "PATCH",
        body: JSON.stringify({
          full_name: editFullName,
          phone: editPhone,
          email: editEmail,
          address: editAddress,
          preferred_contact_method: editContact,
          notes: editNotes,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer", activeOrganization?.id, customerId] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      setEditingCustomer(false);
      setCustomerEditError("");
    },
    onError: (err) => {
      setCustomerEditError(err instanceof Error ? err.message : "Could not update customer.");
    },
  });

  const toggleArchiveMutation = useMutation({
    mutationFn: () => {
      if (customer?.is_archived) {
        return apiRequest<Customer>(`/customers/${customerId}/`, {
          method: "PATCH",
          body: JSON.stringify({ is_archived: false }),
        });
      }
      return apiRequest<Customer>(`/customers/${customerId}/`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer", activeOrganization?.id, customerId] });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
    onError: (err) => {
      setCustomerEditError(err instanceof Error ? err.message : "Could not update archive status.");
    },
  });

  function openNewMeasurementForm() {
    setEditingProfile(null);
    setLabel("Primary Measurements");
    setUnitSystem(activeOrganization?.preferred_unit || "cm");
    setNotes("");
    setFieldInputs({});
    setMeasureError("");
    setShowRecordForm(true);
  }

  function openReviseForm(profile: MeasurementProfile) {
    setEditingProfile(profile);
    setLabel(profile.label);
    setUnitSystem(profile.unit_system);
    setNotes(profile.notes);
    const initial: Record<string, string> = {};
    profile.values.forEach((v) => {
      initial[v.field_key] = v.text_value || (v.numeric_value ?? "");
    });
    setFieldInputs(initial);
    setMeasureError("");
    setShowRecordForm(true);
  }

  const saveMeasurementMutation = useMutation({
    mutationFn: async () => {
      const payloadValues = activeFields
        .map((f) => {
          const raw = (fieldInputs[f.key] || "").trim();
          if (!raw) return null;
          if (f.unit_type === "text") {
            return { field_key: f.key, text_value: raw };
          }
          return { field_key: f.key, numeric_value: raw };
        })
        .filter(Boolean);

      if (editingProfile) {
        return apiRequest<MeasurementProfile>(
          `/customers/${customerId}/measurements/${editingProfile.id}/`,
          {
            method: "PATCH",
            body: JSON.stringify({
              label,
              unit_system: unitSystem,
              notes,
              status: "verified",
              values: payloadValues,
            }),
          }
        );
      }

      if (!activeTemplate?.latest_version?.id) {
        throw new Error("No active measurement template version available.");
      }

      return apiRequest<MeasurementProfile>(`/customers/${customerId}/measurements/`, {
        method: "POST",
        body: JSON.stringify({
          template_version_id: activeTemplate.latest_version.id,
          label,
          unit_system: unitSystem,
          status: "verified",
          notes,
          values: payloadValues,
        }),
      });
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["customer-measurements", activeOrganization?.id, customerId] });
      setSelectedProfileId(saved.id);
      setShowRecordForm(false);
      setEditingProfile(null);
      setMeasureError("");
    },
    onError: (err) => {
      setMeasureError(err instanceof Error ? err.message : "Could not save measurements.");
    },
  });

  const verifyMutation = useMutation({
    mutationFn: (profileId: string) =>
      apiRequest<MeasurementProfile>(`/customers/${customerId}/measurements/${profileId}/verify/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["customer-measurements", activeOrganization?.id, customerId] });
      setSelectedProfileId(saved.id);
    },
  });

  const createRequestMutation = useMutation({
    mutationFn: () => {
      const versionId =
        activeTemplate?.latest_version?.id || templates[0]?.latest_version?.id;
      if (!versionId) throw new Error("No template available.");
      return apiRequest<MeasurementRequestItem>("/measurement-requests/", {
        method: "POST",
        body: JSON.stringify({
          customer_id: customerId,
          template_version_id: versionId,
          expires_in_hours: 72,
        }),
      });
    },
    onSuccess: (req) => {
      queryClient.invalidateQueries({
        queryKey: ["customer-measurement-requests", activeOrganization?.id, customerId],
      });
      if (req.public_path && typeof window !== "undefined") {
        setGeneratedLink(`${window.location.origin}${req.public_path}`);
      }
      setRequestError("");
    },
    onError: (err) => {
      setRequestError(err instanceof Error ? err.message : "Could not create request link.");
    },
  });

  const revokeRequestMutation = useMutation({
    mutationFn: (requestId: string) =>
      apiRequest(`/measurement-requests/${requestId}/revoke/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["customer-measurement-requests", activeOrganization?.id, customerId],
      });
    },
  });

  const createShareMutation = useMutation({
    mutationFn: () => {
      if (!displayedProfile) throw new Error("Select a verified profile to share.");
      return apiRequest<MeasurementShareLink>("/measurement-shares/", {
        method: "POST",
        body: JSON.stringify({
          profile_id: displayedProfile.id,
          recipient_label: shareRecipient,
          consent_confirmed: shareConsent,
          expires_in_days: 14,
        }),
      });
    },
    onSuccess: (share) => {
      queryClient.invalidateQueries({
        queryKey: ["customer-measurement-shares", activeOrganization?.id, customerId],
      });
      if (share.public_path && typeof window !== "undefined") {
        setGeneratedShareLink(`${window.location.origin}${share.public_path}`);
      }
      setShareRecipient("");
      setShareConsent(false);
      setShowSharePanel(false);
      setShareError("");
    },
    onError: (err) => {
      setShareError(err instanceof Error ? err.message : "Could not generate Fit Passport link.");
    },
  });

  const revokeShareMutation = useMutation({
    mutationFn: (shareId: string) =>
      apiRequest(`/measurement-shares/${shareId}/revoke/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["customer-measurement-shares", activeOrganization?.id, customerId],
      });
    },
  });

  const importShareMutation = useMutation({
    mutationFn: () =>
      apiRequest<MeasurementProfile>(`/customers/${customerId}/measurements/import-from-share/`, {
        method: "POST",
        body: JSON.stringify({ token: importToken }),
      }),
    onSuccess: (imported) => {
      queryClient.invalidateQueries({
        queryKey: ["customer-measurements", activeOrganization?.id, customerId],
      });
      setSelectedProfileId(imported.id);
      setImportToken("");
      setShowImportPanel(false);
      setImportError("");
    },
    onError: (err) => {
      setImportError(err instanceof Error ? err.message : "Could not import Fit Passport.");
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:gap-3">
            <Link href="/customers" className="self-start sm:mt-1">
              <Button variant="outline" size="sm">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            </Link>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="mezer-eyebrow">Customer Fit Passport</span>
                {customer?.is_archived && <StatusBadge status="superseded" />}
              </div>
              <h1 className="mt-1 break-words text-xl font-extrabold tracking-tight text-plum sm:text-3xl">
                {loadingCustomer ? "Loading customer..." : customer?.full_name}
              </h1>
              {customer && (
                <p className="mt-0.5 text-sm text-ink-soft">
                  {customer.phone}
                  {customer.email ? ` · ${customer.email}` : ""} · Preferred:{" "}
                  <span className="capitalize">{customer.preferred_contact_method}</span>
                  {customer.address ? ` · ${customer.address}` : ""}
                </p>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            {customer && (
              <Button variant="outline" size="sm" className="w-full sm:w-auto" onClick={openCustomerEdit}>
                <Edit3 className="h-4 w-4" />
                Edit details
              </Button>
            )}
            {customer && canArchive && (
              <Button
                variant={customer.is_archived ? "secondary" : "outline"}
                size="sm"
                className="w-full sm:w-auto"
                disabled={toggleArchiveMutation.isPending}
                onClick={() => toggleArchiveMutation.mutate()}
              >
                {customer.is_archived ? (
                  <>
                    <RotateCcw className="h-4 w-4" /> Restore
                  </>
                ) : (
                  <>
                    <Archive className="h-4 w-4" /> Archive
                  </>
                )}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="w-full sm:w-auto"
              onClick={() => createRequestMutation.mutate()}
            >
              <Link2 className="h-4 w-4" />
              Request measurements
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="w-full sm:w-auto"
              onClick={() => {
                setShowImportPanel((v) => !v);
                setImportError("");
              }}
            >
              <Download className="h-4 w-4" />
              Import Fit Passport
            </Button>
            <Button
              size="sm"
              className="col-span-2 w-full sm:col-span-1 sm:w-auto"
              onClick={openNewMeasurementForm}
            >
              <Plus className="h-4 w-4" />
              Record measurements
            </Button>
          </div>
        </div>

        {/* Inline Edit Customer Panel */}
        {editingCustomer && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <h2 className="text-base font-bold text-plum">Edit Customer Profile</h2>
              <Button variant="ghost" size="sm" onClick={() => setEditingCustomer(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  updateCustomerMutation.mutate();
                }}
              >
                {customerEditError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {customerEditError}
                  </div>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="edit-cust-name">Full name</Label>
                    <Input
                      id="edit-cust-name"
                      required
                      value={editFullName}
                      onChange={(e) => setEditFullName(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit-cust-phone">Phone</Label>
                    <Input
                      id="edit-cust-phone"
                      required
                      value={editPhone}
                      onChange={(e) => setEditPhone(e.target.value)}
                    />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="edit-cust-email">Email</Label>
                    <Input
                      id="edit-cust-email"
                      type="email"
                      value={editEmail}
                      onChange={(e) => setEditEmail(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit-cust-contact">Preferred contact</Label>
                    <Select
                      id="edit-cust-contact"
                      value={editContact}
                      onChange={(e) =>
                        setEditContact(e.target.value as "phone" | "whatsapp" | "email" | "sms")
                      }
                    >
                      <option value="whatsapp">WhatsApp</option>
                      <option value="phone">Phone</option>
                      <option value="sms">SMS</option>
                      <option value="email">Email</option>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label htmlFor="edit-cust-address">Address</Label>
                  <Input
                    id="edit-cust-address"
                    value={editAddress}
                    onChange={(e) => setEditAddress(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="edit-cust-notes">Notes</Label>
                  <Textarea
                    id="edit-cust-notes"
                    rows={2}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setEditingCustomer(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={updateCustomerMutation.isPending}>
                    {updateCustomerMutation.isPending ? "Saving..." : "Save changes"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {customer?.notes && !editingCustomer && (
          <div className="rounded-mezer-sm border border-line bg-white px-5 py-3 text-sm text-ink-soft shadow-mezer-sm">
            <span className="font-bold text-plum">Client Notes:</span> {customer.notes}
          </div>
        )}

        {requestError && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {requestError}
          </div>
        )}

        {generatedLink && (
          <Card className="border-brand-300 bg-plum text-white">
            <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="mezer-eyebrow-light">
                  Secure Customer Measurement Link (72h expiry)
                </div>
                <div className="mt-1.5 truncate font-mono text-xs text-white/90">{generatedLink}</div>
              </div>
              <Button
                size="sm"
                variant="light"
                onClick={() => navigator.clipboard?.writeText(generatedLink)}
              >
                <ClipboardCopy className="h-4 w-4" />
                Copy link
              </Button>
            </CardContent>
          </Card>
        )}

        {generatedShareLink && (
          <Card className="border-brand-300 bg-plum text-white">
            <CardContent className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="mezer-eyebrow-light">
                  Portable Fit Passport Share Link (14-day expiry)
                </div>
                <div className="mt-1.5 truncate font-mono text-xs text-white/90">
                  {generatedShareLink}
                </div>
              </div>
              <Button
                size="sm"
                variant="light"
                onClick={() => navigator.clipboard?.writeText(generatedShareLink)}
              >
                <ClipboardCopy className="h-4 w-4" />
                Copy link
              </Button>
            </CardContent>
          </Card>
        )}

        {showImportPanel && (
          <Card className="border-brand-300">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-plum">Import Shared Fit Passport</h2>
                <p className="text-xs text-ink-faint">
                  Paste a customer&apos;s consented `/fit/...` link or token. Imported profiles start in{" "}
                  <strong>Needs Review</strong> until you verify them.
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setShowImportPanel(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  importShareMutation.mutate();
                }}
              >
                {importError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2 text-xs text-red-700">
                    {importError}
                  </div>
                )}
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Input
                    required
                    placeholder="Paste Fit Passport URL (e.g. http://localhost:3000/fit/...) or token"
                    className="mt-0 flex-1"
                    value={importToken}
                    onChange={(e) => setImportToken(e.target.value)}
                  />
                  <Button type="submit" disabled={importShareMutation.isPending}>
                    {importShareMutation.isPending ? "Importing..." : "Import for review"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {showSharePanel && displayedProfile && (
          <Card className="border-brand-300">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-plum">
                  Share Fit Passport · {displayedProfile.label} (v{displayedProfile.version_number})
                </h2>
                <p className="text-xs text-ink-faint">
                  Generates a read-only, revocable link containing only measurement values—no contact PII.
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setShowSharePanel(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  createShareMutation.mutate();
                }}
              >
                {shareError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2 text-xs text-red-700">
                    {shareError}
                  </div>
                )}
                <div>
                  <Label htmlFor="share-recipient">Recipient / purpose label (optional)</Label>
                  <Input
                    id="share-recipient"
                    placeholder="e.g. Shared with customer for wedding designer"
                    value={shareRecipient}
                    onChange={(e) => setShareRecipient(e.target.value)}
                  />
                </div>
                <label className="flex items-start gap-2.5 rounded-mezer-sm border border-line bg-surface-blush p-3.5 text-xs text-ink">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-brand-700"
                    checked={shareConsent}
                    onChange={(e) => setShareConsent(e.target.checked)}
                  />
                  <span>
                    I confirm the customer has explicitly consented to generating a portable Fit
                    Passport share link for this verified measurement profile.
                  </span>
                </label>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowSharePanel(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createShareMutation.isPending}>
                    {createShareMutation.isPending ? "Generating..." : "Create Fit Passport link"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {showRecordForm && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-plum">
                  {editingProfile
                    ? `Revise Measurements (creates v${editingProfile.version_number + 1})`
                    : "Record New Measurement Profile"}
                </h2>
                <p className="text-xs text-ink-faint">
                  {editingProfile
                    ? "Previous measurement versions remain preserved in history for confirmed orders."
                    : "Select a template and unit system."}
                </p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowRecordForm(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  saveMeasurementMutation.mutate();
                }}
              >
                {measureError && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                    {measureError}
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-3">
                  {!editingProfile && (
                    <div>
                      <Label htmlFor="m-template">Template</Label>
                      <Select
                        id="m-template"
                        value={activeTemplate?.id || ""}
                        onChange={(e) => {
                          setSelectedTemplateId(e.target.value);
                          setFieldInputs({});
                        }}
                      >
                        {templates.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name} ({t.category})
                          </option>
                        ))}
                      </Select>
                    </div>
                  )}
                  <div>
                    <Label htmlFor="m-label">Profile label</Label>
                    <Input
                      id="m-label"
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="m-unit">Unit system</Label>
                    <Select
                      id="m-unit"
                      value={unitSystem}
                      onChange={(e) => setUnitSystem(e.target.value as UnitSystem)}
                    >
                      <option value="cm">Centimetres (cm)</option>
                      <option value="in">Inches (in)</option>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
                  {activeFields.map((field) => (
                    <div key={field.id} className="rounded-mezer-sm border border-line bg-surface-blush p-3.5">
                      <Label htmlFor={`field-${field.key}`} className="flex items-center justify-between">
                        <span className="text-ink">
                          {field.label}
                          {field.is_required && <span className="ml-1 text-brand-600">*</span>}
                        </span>
                        <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-bold uppercase text-brand-700">
                          {field.unit_type === "text" ? "text" : unitSystem}
                        </span>
                      </Label>
                      <Input
                        id={`field-${field.key}`}
                        type={field.unit_type === "text" ? "text" : "number"}
                        step={field.unit_type === "text" ? undefined : "0.01"}
                        required={field.is_required}
                        className="mt-2 bg-white"
                        value={fieldInputs[field.key] || ""}
                        onChange={(e) =>
                          setFieldInputs((prev) => ({ ...prev, [field.key]: e.target.value }))
                        }
                      />
                      {field.guidance_text && (
                        <p className="mt-1.5 text-[11px] leading-snug text-ink-faint">
                          {field.guidance_text}
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                <div>
                  <Label htmlFor="m-notes">Fitting / measurement notes</Label>
                  <Textarea
                    id="m-notes"
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="e.g. Prefers slim sleeve, slight shoulder slope..."
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowRecordForm(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={saveMeasurementMutation.isPending}>
                    {saveMeasurementMutation.isPending
                      ? "Saving..."
                      : editingProfile
                      ? "Save as new version"
                      : "Save verified measurements"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Selected Measurement Profile Detail */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                  <Ruler className="h-4 w-4" />
                </div>
                <h2 className="text-base font-bold text-plum">
                  {displayedProfile
                    ? `${displayedProfile.label} · v${displayedProfile.version_number}`
                    : "Measurement Profile"}
                </h2>
              </div>
              {displayedProfile && (
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={displayedProfile.status} />
                  {displayedProfile.status !== "verified" &&
                    displayedProfile.status !== "superseded" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => verifyMutation.mutate(displayedProfile.id)}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                        Verify
                      </Button>
                    )}
                  {displayedProfile.status === "verified" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setShowSharePanel(true);
                        setShareError("");
                      }}
                    >
                      <Share2 className="h-3.5 w-3.5 text-brand-700" />
                      Share Fit Passport
                    </Button>
                  )}
                  {displayedProfile.status !== "superseded" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openReviseForm(displayedProfile)}
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                      Edit / New version
                    </Button>
                  )}
                </div>
              )}
            </CardHeader>
            <CardContent>
              {loadingProfiles ? (
                <p className="text-sm text-ink-faint">Loading measurements...</p>
              ) : !displayedProfile ? (
                <div className="py-10 text-center">
                  <p className="text-sm text-ink-soft">
                    No measurements recorded for this customer yet.
                  </p>
                  <Button className="mt-4" size="sm" onClick={openNewMeasurementForm}>
                    Record first measurement profile
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-3 text-xs text-ink-faint">
                    <span className="rounded-full bg-surface px-3 py-1 font-medium text-ink-soft">
                      {displayedProfile.template_name}
                    </span>
                    <span className="rounded-full bg-surface-blush px-3 py-1 font-semibold uppercase text-brand-700">
                      {displayedProfile.unit_system}
                    </span>
                    <span className="rounded-full bg-surface px-3 py-1">
                      Source: {displayedProfile.source}
                    </span>
                    <span className="rounded-full bg-surface px-3 py-1">
                      {formatDateTime(displayedProfile.measured_at)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                    {displayedProfile.values.map((val) => (
                      <div
                        key={val.id}
                        className="rounded-mezer-sm border border-line-soft bg-surface-blush p-3.5"
                      >
                        <div className="text-xs font-medium text-ink-soft">{val.field_label}</div>
                        <div className="mt-1 text-lg font-extrabold tracking-tight text-plum">
                          {val.text_value || `${val.numeric_value} ${val.unit}`}
                        </div>
                      </div>
                    ))}
                  </div>

                  {displayedProfile.notes && (
                    <div className="rounded-mezer-sm border border-line-soft bg-paper p-3.5 text-xs text-ink-soft">
                      <span className="font-bold text-plum">Notes:</span> {displayedProfile.notes}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Measurement Version History & Requests */}
          <div className="space-y-6">
            <Card className="overflow-hidden">
              <CardHeader className="flex flex-row items-center gap-2">
                <History className="h-4 w-4 text-brand-700" />
                <h2 className="text-base font-bold text-plum">Measurement History</h2>
              </CardHeader>
              <CardContent className="divide-y divide-line-soft p-0">
                {profiles.length === 0 ? (
                  <p className="p-6 text-sm text-ink-faint">No history yet.</p>
                ) : (
                  profiles.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setSelectedProfileId(p.id)}
                      className={`flex w-full items-center justify-between px-6 py-3.5 text-left transition-colors hover:bg-surface-blush ${
                        displayedProfile?.id === p.id ? "bg-surface-blush" : ""
                      }`}
                    >
                      <div>
                        <div className="text-sm font-semibold text-plum">
                          v{p.version_number} · {p.label}
                        </div>
                        <div className="text-xs text-ink-faint">
                          {p.unit_system} · {formatDateTime(p.measured_at)}
                        </div>
                      </div>
                      <StatusBadge status={p.status} />
                    </button>
                  ))
                )}
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader>
                <h2 className="text-base font-bold text-plum">Shared Fit Passports</h2>
              </CardHeader>
              <CardContent className="divide-y divide-line-soft p-0">
                {!sharesData?.results.length ? (
                  <p className="p-6 text-sm text-ink-faint">No Fit Passports shared yet.</p>
                ) : (
                  sharesData.results.map((share) => (
                    <div key={share.id} className="flex items-center justify-between px-6 py-3.5">
                      <div>
                        <div className="text-xs font-semibold text-plum">
                          v{share.profile_version} · {share.recipient_label || "Portable share"}
                        </div>
                        <div className="text-[11px] text-ink-faint">
                          Views: {share.access_count} · Expires {formatDateTime(share.expires_at)}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={share.status} />
                        {share.status === "active" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => revokeShareMutation.mutate(share.id)}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader>
                <h2 className="text-base font-bold text-plum">Measurement Requests</h2>
              </CardHeader>
              <CardContent className="divide-y divide-line-soft p-0">
                {!requestsData?.results.length ? (
                  <p className="p-6 text-sm text-ink-faint">No links sent yet.</p>
                ) : (
                  requestsData.results.map((req) => (
                    <div key={req.id} className="flex items-center justify-between px-6 py-3.5">
                      <div>
                        <div className="text-xs font-semibold text-plum">
                          {req.template_name}
                        </div>
                        <div className="text-[11px] text-ink-faint">
                          Expires {formatDateTime(req.expires_at)}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={req.status} />
                        {req.status === "pending" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => revokeRequestMutation.mutate(req.id)}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Guided Reference Photos (Phase 4 Milestone 1) */}
        <CustomerReferencePhotosSection
          customerId={customerId}
          activeProfileId={displayedProfile?.id}
        />

        {/* Orders & Appointments */}
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between">
              <h2 className="text-base font-bold text-plum">Customer Orders</h2>
              <Link href={`/orders?customer=${customerId}`}>
                <Button size="sm" variant="outline">
                  New order
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="divide-y divide-line-soft p-0">
              {!ordersData?.results.length ? (
                <p className="p-6 text-sm text-ink-faint">No orders for this customer yet.</p>
              ) : (
                ordersData.results.map((order) => (
                  <Link
                    key={order.id}
                    href={`/orders/${order.id}`}
                    className="flex items-center justify-between px-6 py-4 transition-colors hover:bg-surface-blush"
                  >
                    <div>
                      <div className="text-sm font-semibold text-plum">
                        {order.order_number} · {order.garment_type}
                      </div>
                      <div className="mt-0.5 text-xs text-ink-soft">
                        Quote: {formatCurrency(order.quoted_amount, order.currency)} · Deposit:{" "}
                        {formatCurrency(order.deposit_amount, order.currency)}
                      </div>
                    </div>
                    <StatusBadge status={order.status} />
                  </Link>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-brand-700" />
                <h2 className="text-base font-bold text-plum">Fittings &amp; Appointments</h2>
              </div>
              <Link href={`/appointments?customer=${customerId}`}>
                <Button size="sm" variant="outline">
                  Schedule fitting
                </Button>
              </Link>
            </CardHeader>
            <CardContent className="divide-y divide-line-soft p-0">
              {!appointmentsData?.results.length ? (
                <p className="p-6 text-sm text-ink-faint">No appointments scheduled yet.</p>
              ) : (
                appointmentsData.results.map((appt) => (
                  <div key={appt.id} className="flex items-center justify-between px-6 py-4">
                    <div>
                      <div className="text-sm font-semibold text-plum">{appt.title}</div>
                      <div className="mt-0.5 text-xs text-ink-soft">
                        {formatDateTime(appt.scheduled_at)} · {appt.location}
                      </div>
                    </div>
                    <StatusBadge status={appt.status} />
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
