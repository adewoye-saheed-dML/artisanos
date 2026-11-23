"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, LocateFixed, MapPin, PlusCircle, Search, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import type {
  LocationResolvedResponse,
  LocationSearchResponse,
  NigerianLGA,
  NigerianState,
  NigerianWard,
  PollingUnit,
} from "@/types/api";

export interface NigeriaLocationValue {
  stateId: string;
  lgaId: string;
  wardId: string;
  pollingUnitId: string;
}

export interface DetectedLocationMeta {
  landmark?: string;
  latitude?: string;
  longitude?: string;
  nearbyArtisanCount?: number;
  matchSource?: string;
}

interface NigeriaLocationPickerProps {
  value: NigeriaLocationValue;
  onChange: (next: NigeriaLocationValue) => void;
  onDetectedMeta?: (meta: DetectedLocationMeta) => void;
  showQuickSearch?: boolean;
  showAutoDetect?: boolean;
  autoDetectOnMount?: boolean;
  allowCreateNew?: boolean;
  disabled?: boolean;
  compact?: boolean;
  idPrefix?: string;
}

export function NigeriaLocationPicker({
  value,
  onChange,
  onDetectedMeta,
  showQuickSearch = true,
  showAutoDetect = true,
  autoDetectOnMount = false,
  allowCreateNew = false,
  disabled = false,
  compact = false,
  idPrefix = "ng-loc",
}: NigeriaLocationPickerProps) {
  const queryClient = useQueryClient();
  const [quickQuery, setQuickQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Auto-detect state
  const [detecting, setDetecting] = useState(false);
  const [detectBanner, setDetectBanner] = useState("");
  const [detectError, setDetectError] = useState("");
  const didAutoDetectRef = useRef(false);

  // Add missing Ward / Polling Unit inline state (for all 774 LGAs)
  const [showAddForm, setShowAddForm] = useState(false);
  const [customWardName, setCustomWardName] = useState("");
  const [customPuName, setCustomPuName] = useState("");
  const [customError, setCustomError] = useState("");

  const { data: states } = useQuery({
    queryKey: ["ng-states"],
    queryFn: () => apiRequest<NigerianState[]>("/locations/states/", { skipOrgHeader: true }),
    staleTime: 1000 * 60 * 30,
  });

  const { data: lgas } = useQuery({
    queryKey: ["ng-lgas", value.stateId],
    queryFn: () =>
      apiRequest<NigerianLGA[]>(`/locations/lgas/?state=${value.stateId}`, {
        skipOrgHeader: true,
      }),
    enabled: !!value.stateId,
    staleTime: 1000 * 60 * 30,
  });

  const { data: wards } = useQuery({
    queryKey: ["ng-wards", value.lgaId],
    queryFn: () =>
      apiRequest<NigerianWard[]>(`/locations/wards/?lga=${value.lgaId}`, {
        skipOrgHeader: true,
      }),
    enabled: !!value.lgaId,
    staleTime: 1000 * 60 * 5,
  });

  const { data: pollingUnits } = useQuery({
    queryKey: ["ng-pus", value.wardId],
    queryFn: () =>
      apiRequest<PollingUnit[]>(`/locations/polling-units/?ward=${value.wardId}`, {
        skipOrgHeader: true,
      }),
    enabled: !!value.wardId,
    staleTime: 1000 * 60 * 5,
  });

  const trimmedQuery = quickQuery.trim();
  const { data: searchResults } = useQuery({
    queryKey: ["ng-loc-search", trimmedQuery, value.stateId, value.lgaId, value.wardId],
    queryFn: () => {
      const params = new URLSearchParams({ q: trimmedQuery });
      if (value.stateId) params.set("state", value.stateId);
      if (value.lgaId) params.set("lga", value.lgaId);
      if (value.wardId) params.set("ward", value.wardId);
      return apiRequest<LocationSearchResponse>(
        `/locations/search/?${params.toString()}`,
        { skipOrgHeader: true }
      );
    },
    enabled: showQuickSearch && trimmedQuery.length >= 2 && !disabled,
  });

  const handleAutoDetect = useCallback(
    async (silent = false) => {
      if (typeof window === "undefined" || !("geolocation" in navigator)) {
        if (!silent) {
          setDetectError("Your browser does not support GPS auto-detection. Select your State & LGA below.");
        }
        return;
      }
      setDetecting(true);
      setDetectError("");
      if (!silent) setDetectBanner("");

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude.toFixed(6);
          const lng = position.coords.longitude.toFixed(6);
          try {
            const resolved = await apiRequest<LocationResolvedResponse>("/locations/detect/", {
              method: "POST",
              skipOrgHeader: true,
              body: JSON.stringify({ latitude: lat, longitude: lng }),
            });

            if (resolved.state && resolved.lga) {
              queryClient.invalidateQueries({ queryKey: ["ng-wards", resolved.lga.id] });
              if (resolved.ward) {
                queryClient.invalidateQueries({ queryKey: ["ng-pus", resolved.ward.id] });
              }
              onChange({
                stateId: resolved.state.id,
                lgaId: resolved.lga.id,
                wardId: resolved.ward?.id || "",
                pollingUnitId: resolved.polling_unit?.id || "",
              });
              onDetectedMeta?.({
                landmark: resolved.landmark,
                latitude: lat,
                longitude: lng,
                nearbyArtisanCount: resolved.nearby_artisan_count,
                matchSource: resolved.match_source,
              });
              const locSummary = [
                resolved.polling_unit?.name,
                resolved.ward ? `${resolved.ward.name} Ward` : "",
                resolved.lga.name,
                resolved.state.name,
              ]
                .filter(Boolean)
                .join(" · ");
              setDetectBanner(
                `Detected: ${locSummary}${
                  resolved.nearby_artisan_count > 0
                    ? ` (${resolved.nearby_artisan_count} nearby ${
                        resolved.nearby_artisan_count === 1 ? "artisan" : "artisans"
                      })`
                    : ""
                }`
              );
            } else if (!silent) {
              setDetectError(
                "Could not map your GPS point to a Nigerian Ward yet. Choose your State & LGA below and add your Ward/Polling Unit."
              );
            }
          } catch (err) {
            if (!silent) {
              setDetectError(
                err instanceof Error ? err.message : "Could not auto-detect location."
              );
            }
          } finally {
            setDetecting(false);
          }
        },
        (geoErr) => {
          setDetecting(false);
          if (!silent) {
            if (geoErr.code === geoErr.PERMISSION_DENIED) {
              setDetectError(
                "Location permission was blocked. Allow location access or pick your State → LGA → Ward below."
              );
            } else {
              setDetectError(
                "Could not read GPS signal. Select your State → LGA → Ward → Polling Unit below."
              );
            }
          }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
      );
    },
    [onChange, onDetectedMeta, queryClient]
  );

  // Optionally attempt silent auto-detect on mount (only when browser permission is already granted)
  useEffect(() => {
    if (!autoDetectOnMount || disabled || didAutoDetectRef.current) return;
    if (value.stateId || value.wardId || value.pollingUnitId) return;
    didAutoDetectRef.current = true;

    if (typeof navigator !== "undefined" && navigator.permissions?.query) {
      navigator.permissions
        .query({ name: "geolocation" as PermissionName })
        .then((perm) => {
          if (perm.state === "granted") {
            handleAutoDetect(true);
          }
        })
        .catch(() => {
          // Ignore permissions API unsupported error
        });
    }
  }, [autoDetectOnMount, disabled, handleAutoDetect, value.pollingUnitId, value.stateId, value.wardId]);

  const ensureMutation = useMutation({
    mutationFn: () =>
      apiRequest<LocationResolvedResponse>("/locations/ensure/", {
        method: "POST",
        skipOrgHeader: true,
        body: JSON.stringify({
          lga: value.lgaId,
          ward_name: customWardName.trim(),
          polling_unit_name: customPuName.trim(),
        }),
      }),
    onSuccess: (resolved) => {
      if (resolved.state && resolved.lga && resolved.ward) {
        queryClient.invalidateQueries({ queryKey: ["ng-wards", resolved.lga.id] });
        queryClient.invalidateQueries({ queryKey: ["ng-pus", resolved.ward.id] });
        onChange({
          stateId: resolved.state.id,
          lgaId: resolved.lga.id,
          wardId: resolved.ward.id,
          pollingUnitId: resolved.polling_unit?.id || "",
        });
        setDetectBanner(
          `Mapped: ${
            resolved.polling_unit ? `${resolved.polling_unit.name} · ` : ""
          }${resolved.ward.name} Ward, ${resolved.lga.name}`
        );
      }
      setCustomWardName("");
      setCustomPuName("");
      setCustomError("");
      setShowAddForm(false);
    },
    onError: (err) => {
      setCustomError(err instanceof Error ? err.message : "Could not save Ward / Polling Unit.");
    },
  });

  const hasSearchHits =
    (searchResults?.polling_units?.length ?? 0) > 0 || (searchResults?.wards?.length ?? 0) > 0;
  const hasSelection = !!(value.stateId || value.lgaId || value.wardId || value.pollingUnitId);
  const selectedWardObj = wards?.find((w) => w.id === value.wardId);

  return (
    <div className="space-y-3">
      {/* Top Row: Quick Search + One-Tap GPS Auto-Detect */}
      {(showQuickSearch || showAutoDetect) && !disabled && (
        <div className="flex flex-col gap-2 sm:flex-row">
          {showQuickSearch && (
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-ink-faint" />
              <Input
                id={`${idPrefix}-quick`}
                value={quickQuery}
                onFocus={() => setDropdownOpen(true)}
                onChange={(e) => {
                  setQuickQuery(e.target.value);
                  setDropdownOpen(true);
                }}
                placeholder="Search Polling Unit, Ward, or street (e.g. Allen, Wuse, Surulere, Yaba)..."
                className="mt-0 bg-white pl-10 pr-9"
              />
              {quickQuery && (
                <button
                  type="button"
                  aria-label="Clear location search"
                  onClick={() => {
                    setQuickQuery("");
                    setDropdownOpen(false);
                  }}
                  className="absolute right-3 top-2.5 rounded-full p-0.5 text-ink-faint hover:bg-surface-blush hover:text-plum"
                >
                  <X className="h-4 w-4" />
                </button>
              )}

              {dropdownOpen && trimmedQuery.length >= 2 && (
                <div className="absolute left-0 right-0 z-30 mt-1.5 max-h-72 overflow-y-auto rounded-mezer-sm border border-line bg-white p-2 shadow-card-hover">
                  {!hasSearchHits ? (
                    <div className="px-3 py-3 text-xs text-ink-faint">
                      No saved Ward or Polling Unit matched &ldquo;{trimmedQuery}&rdquo; yet.
                      Select your State &amp; LGA below (all 774 LGAs mapped) to add it.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {searchResults && searchResults.polling_units.length > 0 && (
                        <div>
                          <div className="px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider text-brand-700">
                            Polling Units (Hyper-Local)
                          </div>
                          {searchResults.polling_units.map((pu) => (
                            <button
                              key={pu.id}
                              type="button"
                              onClick={() => {
                                onChange({
                                  stateId: pu.state_id,
                                  lgaId: pu.lga_id,
                                  wardId: pu.ward,
                                  pollingUnitId: pu.id,
                                });
                                setQuickQuery(`${pu.name} (${pu.ward_name}, ${pu.state_name})`);
                                setDropdownOpen(false);
                              }}
                              className="flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-surface-blush"
                            >
                              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600" />
                              <div className="min-w-0">
                                <div className="truncate text-xs font-bold text-plum">
                                  {pu.name}{" "}
                                  <span className="font-mono text-[10px] font-normal text-ink-faint">
                                    [{pu.pu_code}]
                                  </span>
                                </div>
                                <div className="truncate text-[11px] text-ink-soft">
                                  Ward: {pu.ward_name} · {pu.lga_name}, {pu.state_name}
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}

                      {searchResults && searchResults.wards.length > 0 && (
                        <div>
                          <div className="px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider text-ink-faint">
                            Electoral Wards (Registration Areas)
                          </div>
                          {searchResults.wards.map((ward) => (
                            <button
                              key={ward.id}
                              type="button"
                              onClick={() => {
                                onChange({
                                  stateId: ward.state_id,
                                  lgaId: ward.lga,
                                  wardId: ward.id,
                                  pollingUnitId: "",
                                });
                                setQuickQuery(
                                  `${ward.name} Ward (${ward.lga_name}, ${ward.state_name})`
                                );
                                setDropdownOpen(false);
                              }}
                              className="flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left transition-colors hover:bg-surface-blush"
                            >
                              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-plum-soft" />
                              <div className="min-w-0">
                                <div className="truncate text-xs font-bold text-plum">
                                  {ward.name} Ward
                                </div>
                                <div className="truncate text-[11px] text-ink-soft">
                                  {ward.lga_name}, {ward.state_name}
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {showAutoDetect && (
            <Button
              type="button"
              variant="outline"
              size="md"
              disabled={detecting}
              onClick={() => handleAutoDetect(false)}
              className="w-full shrink-0 bg-white sm:w-auto"
            >
              {detecting ? (
                <Loader2 className="h-4 w-4 animate-spin text-brand-700" />
              ) : (
                <LocateFixed className="h-4 w-4 text-brand-700" />
              )}
              {detecting ? "Detecting..." : "Auto-detect my Ward / PU"}
            </Button>
          )}
        </div>
      )}

      {detectBanner && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800">
          {detectBanner}
        </div>
      )}
      {detectError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {detectError}
        </div>
      )}

      {/* Cascading State (37) -> LGA (774) -> Ward -> Polling Unit */}
      <div
        className={
          compact ? "grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4" : "grid gap-3 sm:grid-cols-2"
        }
      >
        <div>
          <Label htmlFor={`${idPrefix}-state`}>State (36 + FCT)</Label>
          <Select
            id={`${idPrefix}-state`}
            disabled={disabled}
            className="bg-white"
            value={value.stateId}
            onChange={(e) =>
              onChange({
                stateId: e.target.value,
                lgaId: "",
                wardId: "",
                pollingUnitId: "",
              })
            }
          >
            <option value="">All Nigerian States</option>
            {states?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label htmlFor={`${idPrefix}-lga`}>LGA (All 774 LGAs)</Label>
          <Select
            id={`${idPrefix}-lga`}
            disabled={disabled || !value.stateId}
            className="bg-white"
            value={value.lgaId}
            onChange={(e) => {
              setShowAddForm(false);
              onChange({
                ...value,
                lgaId: e.target.value,
                wardId: "",
                pollingUnitId: "",
              });
            }}
          >
            <option value="">{value.stateId ? "All LGAs in State" : "Select State first"}</option>
            {lgas?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label htmlFor={`${idPrefix}-ward`}>Ward (Registration Area)</Label>
          <Select
            id={`${idPrefix}-ward`}
            disabled={disabled || !value.lgaId}
            className="bg-white"
            value={value.wardId}
            onChange={(e) =>
              onChange({
                ...value,
                wardId: e.target.value,
                pollingUnitId: "",
              })
            }
          >
            <option value="">
              {!value.lgaId
                ? "Select LGA first"
                : wards && wards.length === 0
                  ? "No wards mapped yet — add yours below"
                  : "All Wards in LGA"}
            </option>
            {wards?.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Label htmlFor={`${idPrefix}-pu`}>Polling Unit (Smallest Area)</Label>
          <Select
            id={`${idPrefix}-pu`}
            disabled={disabled || !value.wardId}
            className="bg-white"
            value={value.pollingUnitId}
            onChange={(e) =>
              onChange({
                ...value,
                pollingUnitId: e.target.value,
              })
            }
          >
            <option value="">
              {!value.wardId
                ? "Select Ward first"
                : pollingUnits && pollingUnits.length === 0
                  ? "No polling units yet — add yours below"
                  : "All Polling Units in Ward"}
            </option>
            {pollingUnits?.map((pu) => (
              <option key={pu.id} value={pu.id}>
                {pu.name} ({pu.pu_code})
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Inline "Map My Exact Ward / Polling Unit" for organic 774-LGA coverage */}
      {allowCreateNew && !disabled && value.lgaId && (
        <div className="space-y-2">
          {!showAddForm ? (
            <button
              type="button"
              onClick={() => {
                setCustomWardName(selectedWardObj?.name || "");
                setCustomError("");
                setShowAddForm(true);
              }}
              className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-700 hover:underline"
            >
              <PlusCircle className="h-3.5 w-3.5" />
              Ward or Polling Unit not listed? Add it to the map
            </button>
          ) : (
            <div className="space-y-2.5 rounded-xl border border-brand-200 bg-white p-3.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-plum">
                  Map your exact Ward &amp; Polling Unit in this LGA
                </span>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="text-ink-faint hover:text-plum"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              {customError && (
                <div className="text-xs font-semibold text-red-600">{customError}</div>
              )}
              <div className="grid gap-2.5 sm:grid-cols-2">
                <div>
                  <Label htmlFor={`${idPrefix}-custom-ward`}>Ward name</Label>
                  <Input
                    id={`${idPrefix}-custom-ward`}
                    placeholder="e.g. Idi-Araba Ward"
                    value={customWardName}
                    onChange={(e) => setCustomWardName(e.target.value)}
                  />
                </div>
                <div>
                  <Label htmlFor={`${idPrefix}-custom-pu`}>Polling Unit / nearest junction</Label>
                  <Input
                    id={`${idPrefix}-custom-pu`}
                    placeholder="e.g. LUTH Main Gate Open Space"
                    value={customPuName}
                    onChange={(e) => setCustomPuName(e.target.value)}
                  />
                </div>
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button
                  size="sm"
                  variant="ghost"
                  className="w-full sm:w-auto"
                  onClick={() => setShowAddForm(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  type="button"
                  className="w-full sm:w-auto"
                  disabled={ensureMutation.isPending || customWardName.trim().length < 2}
                  onClick={() => ensureMutation.mutate()}
                >
                  {ensureMutation.isPending ? "Saving..." : "Pin Ward / Polling Unit"}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {hasSelection && !disabled && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => {
              setQuickQuery("");
              setDetectBanner("");
              onChange({ stateId: "", lgaId: "", wardId: "", pollingUnitId: "" });
            }}
            className="text-xs font-semibold text-brand-700 hover:underline"
          >
            Reset location
          </button>
        </div>
      )}
    </div>
  );
}
