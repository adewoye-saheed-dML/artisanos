"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BadgeCheck,
  Clock,
  ExternalLink,
  FileText,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type {
  GovernmentIdType,
  OrganizationVerificationResponse,
  VerificationDocument,
  VerificationDocumentType,
} from "@/types/api";

export default function VerificationPage() {
  const { activeOrganization, activeMembership, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const canManage =
    activeMembership?.role === "owner" || activeMembership?.role === "manager";

  // KYC Form state
  const [nin, setNin] = useState("");
  const [idType, setIdType] = useState<GovernmentIdType>("nin_slip");
  const [cacNumber, setCacNumber] = useState("");
  const [cacBusinessName, setCacBusinessName] = useState("");
  const [guarantorName, setGuarantorName] = useState("");
  const [guarantorPhone, setGuarantorPhone] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankAccountNumber, setBankAccountNumber] = useState("");
  const [bankAccountName, setBankAccountName] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");

  // Document upload state
  const [docType, setDocType] = useState<VerificationDocumentType>("nin_slip");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["org-verification", activeOrganization?.id],
    queryFn: () =>
      apiRequest<OrganizationVerificationResponse>(
        `/organizations/${activeOrganization?.id}/verification/`
      ),
    enabled: !!activeOrganization?.id,
  });

  const kyc = data?.verification;

  useEffect(() => {
    if (kyc) {
      setIdType(kyc.government_id_type);
      setCacNumber(kyc.cac_number || "");
      setCacBusinessName(kyc.cac_business_name || "");
      setGuarantorName(kyc.guarantor_name || "");
      setGuarantorPhone(kyc.guarantor_phone || "");
      setBankName(kyc.bank_name || "");
      setBankAccountNumber(kyc.bank_account_number || "");
      setBankAccountName(kyc.bank_account_name || "");
    }
  }, [kyc]);

  const submitKycMutation = useMutation({
    mutationFn: () =>
      apiRequest<OrganizationVerificationResponse>(
        `/organizations/${activeOrganization?.id}/verification/`,
        {
          method: "POST",
          body: JSON.stringify({
            nin: nin.trim(),
            government_id_type: idType,
            cac_number: cacNumber.trim(),
            cac_business_name: cacBusinessName.trim(),
            guarantor_name: guarantorName.trim(),
            guarantor_phone: guarantorPhone.trim(),
            bank_name: bankName.trim(),
            bank_account_number: bankAccountNumber.trim(),
            bank_account_name: bankAccountName.trim(),
          }),
        }
      ),
    onSuccess: async () => {
      setSaveError("");
      setSaveMessage("KYC details submitted for Platform Admin review.");
      setNin("");
      queryClient.invalidateQueries({ queryKey: ["org-verification", activeOrganization?.id] });
      await refreshUser();
    },
    onError: (err) => {
      setSaveMessage("");
      setSaveError(err instanceof Error ? err.message : "Could not submit KYC.");
    },
  });

  const uploadDocMutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) throw new Error("Choose a JPG, PNG, WEBP, or PDF file first.");
      const formData = new FormData();
      formData.append("document_type", docType);
      formData.append("file", selectedFile);
      return apiRequest<VerificationDocument>(
        `/organizations/${activeOrganization?.id}/verification/documents/`,
        {
          method: "POST",
          body: formData,
        }
      );
    },
    onSuccess: () => {
      setUploadError("");
      setUploadMessage("Document uploaded securely for admin review.");
      setSelectedFile(null);
      queryClient.invalidateQueries({ queryKey: ["org-verification", activeOrganization?.id] });
    },
    onError: (err) => {
      setUploadMessage("");
      setUploadError(err instanceof Error ? err.message : "Document upload failed.");
    },
  });

  const status = data?.status || activeOrganization?.verification_status || "unsubmitted";

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Status Banner */}
        <div className="relative overflow-hidden rounded-mezer-lg bg-plum px-6 py-6 text-white shadow-card sm:px-8">
          <div className="relative flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="mezer-eyebrow-light">
                <ShieldCheck className="h-3.5 w-3.5 text-brand-300" />
                Anti-Scam Artisan KYC · NIN &amp; CAC
              </div>
              <h1 className="mt-1.5 text-2xl font-extrabold tracking-tight text-white">
                Identity &amp; Business Verification
              </h1>
              <p className="mt-1 max-w-2xl text-xs text-plum-soft">
                Verified artisans earn the public NIN/CAC trust badge, appear in nearby local
                searches, and can accept Escrow-protected customer jobs.
              </p>
            </div>
            <StatusBadge status={status} className="px-4 py-1 text-xs" />
          </div>
        </div>

        {/* Status Callout */}
        {!isLoading && status === "approved" && (
          <div className="flex items-start gap-3 rounded-mezer-sm border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
            <BadgeCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
            <div>
              <div className="font-bold">Verified &amp; Live on the Nigerian Marketplace</div>
              <p className="mt-0.5 text-xs text-emerald-800">
                Your identity (NIN {kyc?.nin_masked}
                {kyc?.cac_number ? ` · CAC ${kyc.cac_number}` : ""}) is approved. Customers in your
                neighborhood can discover your storefront and fund Escrow jobs with you.
              </p>
            </div>
          </div>
        )}

        {!isLoading && status === "pending_review" && (
          <div className="flex items-start gap-3 rounded-mezer-sm border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <Clock className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
            <div>
              <div className="font-bold">KYC Under Platform Review</div>
              <p className="mt-0.5 text-xs text-amber-800">
                Upload your NIN slip, CAC certificate (if applicable), and proof of workshop address
                below so our verification team can approve and publish your storefront.
              </p>
            </div>
          </div>
        )}

        {!isLoading && status === "rejected" && (
          <div className="flex items-start gap-3 rounded-mezer-sm border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-700" />
            <div>
              <div className="font-bold">Verification Rejected — Action Required</div>
              <p className="mt-0.5 text-xs text-red-800">
                Reason: {kyc?.rejection_reason || "Please review your submitted NIN/CAC details and re-upload clear documents."}
              </p>
            </div>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          {/* KYC Identity & Payout Bank Form */}
          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">NIN, CAC &amp; Payout Details</h2>
              <p className="text-xs text-ink-faint">
                {kyc?.nin_masked
                  ? `Saved NIN: ${kyc.nin_masked} (re-enter only if updating)`
                  : "An exact 11-digit Nigerian NIN is mandatory."}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {saveMessage && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs font-semibold text-emerald-800">
                  {saveMessage}
                </div>
              )}
              {saveError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs font-semibold text-red-700">
                  {saveError}
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="kyc-nin">
                    11-digit NIN {kyc?.nin_masked ? `(Current: ${kyc.nin_masked})` : "(Required)"}
                  </Label>
                  <Input
                    id="kyc-nin"
                    maxLength={14}
                    disabled={!canManage}
                    placeholder={kyc?.nin_masked ? "Leave blank to keep existing" : "12345678901"}
                    value={nin}
                    onChange={(e) => setNin(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="kyc-id-type">Government ID type</Label>
                  <Select
                    id="kyc-id-type"
                    disabled={!canManage}
                    value={idType}
                    onChange={(e) => setIdType(e.target.value as GovernmentIdType)}
                  >
                    <option value="nin_slip">NIN Slip / National ID</option>
                    <option value="voters_card">Permanent Voter&apos;s Card (PVC)</option>
                    <option value="drivers_license">Nigerian Driver&apos;s License</option>
                    <option value="intl_passport">Nigerian International Passport</option>
                  </Select>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="kyc-cac">CAC Number (RC / BN / IT)</Label>
                  <Input
                    id="kyc-cac"
                    disabled={!canManage}
                    placeholder="e.g. RC1234567 or BN2345678"
                    value={cacNumber}
                    onChange={(e) => setCacNumber(e.target.value.toUpperCase())}
                  />
                </div>
                <div>
                  <Label htmlFor="kyc-cac-biz">CAC Registered Business Name</Label>
                  <Input
                    id="kyc-cac-biz"
                    disabled={!canManage}
                    value={cacBusinessName}
                    onChange={(e) => setCacBusinessName(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="kyc-g-name">Guarantor name</Label>
                  <Input
                    id="kyc-g-name"
                    disabled={!canManage}
                    value={guarantorName}
                    onChange={(e) => setGuarantorName(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="kyc-g-phone">Guarantor phone</Label>
                  <Input
                    id="kyc-g-phone"
                    disabled={!canManage}
                    value={guarantorPhone}
                    onChange={(e) => setGuarantorPhone(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <Label htmlFor="kyc-bank">Escrow Payout Bank</Label>
                  <Input
                    id="kyc-bank"
                    disabled={!canManage}
                    placeholder="e.g. GTBank"
                    value={bankName}
                    onChange={(e) => setBankName(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="kyc-nuban">10-digit NUBAN</Label>
                  <Input
                    id="kyc-nuban"
                    disabled={!canManage}
                    maxLength={10}
                    value={bankAccountNumber}
                    onChange={(e) => setBankAccountNumber(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor="kyc-acct-name">Account Name</Label>
                  <Input
                    id="kyc-acct-name"
                    disabled={!canManage}
                    value={bankAccountName}
                    onChange={(e) => setBankAccountName(e.target.value)}
                  />
                </div>
              </div>

              {canManage && (
                <div className="flex justify-end pt-1">
                  <Button
                    className="w-full sm:w-auto"
                    onClick={() => submitKycMutation.mutate()}
                    disabled={submitKycMutation.isPending}
                  >
                    {submitKycMutation.isPending ? "Submitting..." : "Save & submit for review"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Supporting Verification Documents Upload */}
          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-plum">Supporting Documents (Anti-Scam Proof)</h2>
              <p className="text-xs text-ink-faint">
                Upload clear photos or PDFs (max 5 MB). Stored privately and visible only to you and
                Platform Admin reviewers.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {uploadMessage && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs font-semibold text-emerald-800">
                  {uploadMessage}
                </div>
              )}
              {uploadError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs font-semibold text-red-700">
                  {uploadError}
                </div>
              )}

              {canManage && (
                <div className="space-y-3 rounded-mezer-sm border border-line bg-surface p-4">
                  <div>
                    <Label htmlFor="doc-type">Document type</Label>
                    <Select
                      id="doc-type"
                      className="bg-white"
                      value={docType}
                      onChange={(e) => setDocType(e.target.value as VerificationDocumentType)}
                    >
                      <option value="nin_slip">NIN Slip / Government ID</option>
                      <option value="cac_certificate">CAC Certificate</option>
                      <option value="utility_bill">Utility Bill / Workshop Address Proof</option>
                      <option value="trade_certificate">Trade Test / Guild Certificate</option>
                      <option value="workshop_photo">Workshop &amp; Artisan Photo</option>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="doc-file">Select file (JPG, PNG, WEBP, or PDF)</Label>
                    <input
                      id="doc-file"
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.pdf"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="mt-1 block w-full text-xs text-ink-soft file:mr-3 file:rounded-full file:border-0 file:bg-plum file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-brand-700"
                    />
                  </div>
                  <Button
                    size="sm"
                    disabled={!selectedFile || !kyc || uploadDocMutation.isPending}
                    onClick={() => uploadDocMutation.mutate()}
                  >
                    <Upload className="h-3.5 w-3.5" />
                    {uploadDocMutation.isPending ? "Uploading..." : "Upload document"}
                  </Button>
                  {!kyc && (
                    <p className="text-[11px] text-amber-700">
                      Submit your NIN details on the left first to enable document upload.
                    </p>
                  )}
                </div>
              )}

              <div className="space-y-2">
                <div className="text-xs font-extrabold uppercase tracking-wider text-ink-faint">
                  Uploaded Documents ({kyc?.documents?.length ?? 0})
                </div>
                {!kyc?.documents?.length ? (
                  <p className="rounded-xl border border-dashed border-line p-4 text-center text-xs text-ink-faint">
                    No documents uploaded yet. Upload your NIN slip and CAC / utility bill to speed
                    up approval.
                  </p>
                ) : (
                  <div className="divide-y divide-line-soft rounded-xl border border-line bg-white">
                    {kyc.documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between gap-2 px-3.5 py-2.5 text-xs"
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <FileText className="h-4 w-4 shrink-0 text-brand-700" />
                          <div className="min-w-0">
                            <div className="truncate font-bold text-plum">
                              {doc.document_type_label}
                            </div>
                            <div className="truncate text-[11px] text-ink-faint">
                              {doc.original_filename} · {formatDateTime(doc.created_at)}
                            </div>
                          </div>
                        </div>
                        <a
                          href={doc.content_path}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex shrink-0 items-center gap-1 font-bold text-brand-700 hover:underline"
                        >
                          View <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
