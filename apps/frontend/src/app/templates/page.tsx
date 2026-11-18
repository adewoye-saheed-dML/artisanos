"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, GitBranch, Plus, Ruler, X } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";
import type { MeasurementTemplate, PaginatedResponse } from "@/types/api";

interface DraftField {
  key: string;
  label: string;
  unit_type: "circumference" | "length" | "width" | "angle" | "numeric" | "text";
  default_unit: "cm" | "in" | "deg" | "none";
  min_value: string;
  max_value: string;
  is_required: boolean;
  guidance_text: string;
}

export default function TemplatesPage() {
  const { activeOrganization, activeMembership } = useAuth();
  const queryClient = useQueryClient();

  const [showCreate, setShowCreate] = useState(false);
  const [versioningTemplate, setVersioningTemplate] = useState<MeasurementTemplate | null>(null);
  const [name, setName] = useState("");
  const [category, setCategory] = useState<"tailoring" | "shoemaking" | "leatherwork" | "other">("tailoring");
  const [description, setDescription] = useState("");
  const [changelog, setChangelog] = useState("");
  const [fields, setFields] = useState<DraftField[]>([
    {
      key: "primary_length",
      label: "Primary Length",
      unit_type: "length",
      default_unit: "cm",
      min_value: "10",
      max_value: "200",
      is_required: true,
      guidance_text: "",
    },
  ]);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["measurement-templates", activeOrganization?.id],
    queryFn: () => apiRequest<PaginatedResponse<MeasurementTemplate>>("/measurement-templates/"),
    enabled: !!activeOrganization?.id,
  });

  const canManage = activeMembership?.role === "owner" || activeMembership?.role === "manager";

  function openNewTemplateForm() {
    setVersioningTemplate(null);
    setName("");
    setDescription("");
    setChangelog("Initial version");
    setFields([
      {
        key: "primary_length",
        label: "Primary Length",
        unit_type: "length",
        default_unit: "cm",
        min_value: "10",
        max_value: "200",
        is_required: true,
        guidance_text: "",
      },
    ]);
    setErrorMsg("");
    setShowCreate(true);
  }

  function openNewVersionBuilder(tpl: MeasurementTemplate) {
    setVersioningTemplate(tpl);
    setChangelog(`Version ${(tpl.latest_version?.version_number ?? 1) + 1} update`);
    const existingFields: DraftField[] = (tpl.latest_version?.fields || []).map((f) => ({
      key: f.key,
      label: f.label,
      unit_type: f.unit_type,
      default_unit: f.default_unit,
      min_value: f.min_value ?? "",
      max_value: f.max_value ?? "",
      is_required: f.is_required,
      guidance_text: f.guidance_text || "",
    }));
    setFields(existingFields.length > 0 ? existingFields : []);
    setErrorMsg("");
    setShowCreate(true);
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const preparedFields = fields.map((f, idx) => ({
        key: f.key,
        label: f.label,
        unit_type: f.unit_type,
        default_unit: f.unit_type === "text" ? "none" : f.default_unit,
        min_value: f.unit_type === "text" || !f.min_value ? null : f.min_value,
        max_value: f.unit_type === "text" || !f.max_value ? null : f.max_value,
        is_required: f.is_required,
        display_order: idx + 1,
        guidance_text: f.guidance_text,
      }));

      if (versioningTemplate) {
        return apiRequest(`/measurement-templates/${versioningTemplate.id}/versions/`, {
          method: "POST",
          body: JSON.stringify({
            changelog,
            fields: preparedFields,
          }),
        });
      }

      return apiRequest<MeasurementTemplate>("/measurement-templates/", {
        method: "POST",
        body: JSON.stringify({
          name,
          category,
          description,
          fields: preparedFields,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["measurement-templates"] });
      setSuccessMsg(
        versioningTemplate
          ? `Published new version for ${versioningTemplate.name}.`
          : "Custom measurement template created."
      );
      setShowCreate(false);
      setVersioningTemplate(null);
      setErrorMsg("");
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : "Could not save template.");
    },
  });

  const cloneMutation = useMutation({
    mutationFn: (tpl: MeasurementTemplate) =>
      apiRequest<MeasurementTemplate>(`/measurement-templates/${tpl.id}/clone/`, {
        method: "POST",
        body: JSON.stringify({ name: `${tpl.name} (${activeOrganization?.name || "Custom"})` }),
      }),
    onSuccess: (cloned) => {
      queryClient.invalidateQueries({ queryKey: ["measurement-templates"] });
      setSuccessMsg(`Cloned "${cloned.name}" into your workspace. You can now publish custom versions.`);
      setErrorMsg("");
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : "Could not clone template.");
    },
  });

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mezer-eyebrow">Fit Schema Engine</div>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-plum sm:text-3xl">
              Measurement Templates
            </h1>
            <p className="mt-1 text-sm text-ink-soft">
              Built-in tailoring, shoemaking, and leatherwork schemas—clone any template or publish
              new versions without breaking historical records.
            </p>
          </div>
          {canManage && (
            <Button onClick={() => (showCreate ? setShowCreate(false) : openNewTemplateForm())}>
              {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {showCreate ? "Close builder" : "New custom template"}
            </Button>
          )}
        </div>

        {successMsg && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
            {successMsg}
          </div>
        )}

        {showCreate && (
          <Card className="border-brand-300">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-plum">
                  {versioningTemplate
                    ? `Publish v${(versioningTemplate.latest_version?.version_number ?? 1) + 1} for ${versioningTemplate.name}`
                    : "Create Custom Template"}
                </h2>
                <p className="text-xs text-ink-faint">
                  Existing measurement profiles linked to older template versions remain immutable.
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {errorMsg && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {errorMsg}
                </div>
              )}

              {versioningTemplate ? (
                <div>
                  <Label htmlFor="tpl-changelog">Version changelog</Label>
                  <Input
                    id="tpl-changelog"
                    value={changelog}
                    onChange={(e) => setChangelog(e.target.value)}
                    placeholder="e.g. Added collar drop and cuff width fields"
                  />
                </div>
              ) : (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <Label htmlFor="tpl-name">Template name</Label>
                      <Input
                        id="tpl-name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Women's Bridal Gown"
                      />
                    </div>
                    <div>
                      <Label htmlFor="tpl-cat">Category</Label>
                      <Select
                        id="tpl-cat"
                        value={category}
                        onChange={(e) =>
                          setCategory(e.target.value as "tailoring" | "shoemaking" | "leatherwork" | "other")
                        }
                      >
                        <option value="tailoring">Tailoring</option>
                        <option value="shoemaking">Shoemaking</option>
                        <option value="leatherwork">Leatherwork</option>
                        <option value="other">Other</option>
                      </Select>
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="tpl-desc">Description</Label>
                    <Textarea
                      id="tpl-desc"
                      rows={2}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                    />
                  </div>
                </>
              )}

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label>Measurement fields ({fields.length})</Label>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setFields((prev) => [
                        ...prev,
                        {
                          key: `field_${prev.length + 1}`,
                          label: `Field ${prev.length + 1}`,
                          unit_type: "length",
                          default_unit: "cm",
                          min_value: "1",
                          max_value: "250",
                          is_required: false,
                          guidance_text: "",
                        },
                      ])
                    }
                  >
                    <Plus className="h-3.5 w-3.5" /> Add field
                  </Button>
                </div>

                {fields.map((field, index) => (
                  <div
                    key={index}
                    className="grid gap-2.5 rounded-mezer-sm border border-line bg-surface-blush p-3.5 sm:grid-cols-5"
                  >
                    <Input
                      className="mt-0 bg-white"
                      placeholder="key_slug"
                      value={field.key}
                      onChange={(e) =>
                        setFields((prev) =>
                          prev.map((item, i) => (i === index ? { ...item, key: e.target.value } : item))
                        )
                      }
                    />
                    <Input
                      className="mt-0 bg-white"
                      placeholder="Label"
                      value={field.label}
                      onChange={(e) =>
                        setFields((prev) =>
                          prev.map((item, i) => (i === index ? { ...item, label: e.target.value } : item))
                        )
                      }
                    />
                    <Select
                      className="mt-0 bg-white"
                      value={field.unit_type}
                      onChange={(e) =>
                        setFields((prev) =>
                          prev.map((item, i) =>
                            i === index
                              ? { ...item, unit_type: e.target.value as DraftField["unit_type"] }
                              : item
                          )
                        )
                      }
                    >
                      <option value="circumference">Circumference</option>
                      <option value="length">Length</option>
                      <option value="width">Width</option>
                      <option value="numeric">Numeric</option>
                      <option value="text">Text</option>
                    </Select>
                    <div className="flex items-center gap-2">
                      <Input
                        className="mt-0 bg-white"
                        placeholder="Min"
                        value={field.min_value}
                        onChange={(e) =>
                          setFields((prev) =>
                            prev.map((item, i) => (i === index ? { ...item, min_value: e.target.value } : item))
                          )
                        }
                      />
                      <Input
                        className="mt-0 bg-white"
                        placeholder="Max"
                        value={field.max_value}
                        onChange={(e) =>
                          setFields((prev) =>
                            prev.map((item, i) => (i === index ? { ...item, max_value: e.target.value } : item))
                          )
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <label className="flex items-center gap-1.5 text-xs font-medium text-ink">
                        <input
                          type="checkbox"
                          className="accent-brand-700"
                          checked={field.is_required}
                          onChange={(e) =>
                            setFields((prev) =>
                              prev.map((item, i) =>
                                i === index ? { ...item, is_required: e.target.checked } : item
                              )
                            )
                          }
                        />
                        Required
                      </label>
                      {fields.length > 1 && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setFields((prev) => prev.filter((_, i) => i !== index))}
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowCreate(false)}>
                  Cancel
                </Button>
                <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                  {saveMutation.isPending
                    ? "Publishing..."
                    : versioningTemplate
                    ? "Publish new version"
                    : "Create template"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {isLoading && <Card className="h-48 animate-pulse bg-white/70" />}

        <div className="grid gap-6 md:grid-cols-2">
          {data?.results.map((tpl) => (
            <Card key={tpl.id} className="flex flex-col justify-between transition-all hover:shadow-card-hover">
              <div>
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-blush text-brand-700">
                        <Ruler className="h-4 w-4" />
                      </div>
                      <h2 className="text-base font-bold text-plum">{tpl.name}</h2>
                    </div>
                    <p className="mt-1.5 text-xs text-ink-faint">
                      Category:{" "}
                      <span className="font-medium capitalize text-ink-soft">{tpl.category}</span> ·{" "}
                      {tpl.is_system ? "System built-in" : "Custom workspace template"} · v
                      {tpl.latest_version?.version_number ?? 1}
                    </p>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3.5">
                  {tpl.description && <p className="text-sm text-ink-soft">{tpl.description}</p>}
                  <div className="flex flex-wrap gap-2">
                    {tpl.latest_version?.fields.map((f) => (
                      <span
                        key={f.id}
                        className="rounded-full border border-line bg-surface-blush px-3 py-1 text-xs font-medium text-ink"
                      >
                        {f.label}
                        {f.is_required ? <span className="ml-0.5 text-brand-600">*</span> : ""}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </div>

              {canManage && (
                <div className="flex items-center justify-end gap-2 border-t border-line-soft px-6 py-3.5">
                  {tpl.is_system ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={cloneMutation.isPending}
                      onClick={() => cloneMutation.mutate(tpl)}
                    >
                      <Copy className="h-3.5 w-3.5" />
                      Clone &amp; customize
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openNewVersionBuilder(tpl)}
                    >
                      <GitBranch className="h-3.5 w-3.5" />
                      Publish v{(tpl.latest_version?.version_number ?? 1) + 1}
                    </Button>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
