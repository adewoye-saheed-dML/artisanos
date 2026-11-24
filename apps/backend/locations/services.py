import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from .utils import haversine_km

# Nigeria geographic bounding box (WGS84) with a small coastal/border margin
NIGERIA_MIN_LAT = Decimal("4.0")
NIGERIA_MAX_LAT = Decimal("14.1")
NIGERIA_MIN_LNG = Decimal("2.6")
NIGERIA_MAX_LNG = Decimal("14.8")

# Lightweight in-process cache for GRID3 ward polygon lookups (key -> (expires_at, payload))
_GRID3_CACHE_TTL_SECONDS = 3600
_GRID3_CACHE_MAX_SIZE = 2048
_grid3_point_cache: dict[tuple[float, float], tuple[float, dict | None]] = {}
_grid3_nearby_cache: dict[tuple[float, float, int], tuple[float, list[dict]]] = {}

_OFFICIAL_SOURCES = {
    NigerianWard.DataSource.INEC,
    NigerianWard.DataSource.GRID3,
    NigerianWard.DataSource.SEED,
}


def clear_location_lookup_caches() -> None:
    """Clear in-process external geocoding caches (useful in tests)."""
    _grid3_point_cache.clear()
    _grid3_nearby_cache.clear()


def is_within_nigeria_bounds(latitude: Decimal | float | None, longitude: Decimal | float | None) -> bool:
    if latitude is None or longitude is None:
        return False
    lat = Decimal(str(latitude))
    lng = Decimal(str(longitude))
    return NIGERIA_MIN_LAT <= lat <= NIGERIA_MAX_LAT and NIGERIA_MIN_LNG <= lng <= NIGERIA_MAX_LNG


def _normalize_label(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(
        r"\b(state|local government area|lga|municipal area council|area council|electoral ward|ward|ra)\b",
        "",
        text,
    )
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def _compact_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_label(value))


def _split_alt_names(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;|]+", raw) if part.strip()]


def match_nigerian_state(hint: str, state_code: str = "") -> NigerianState | None:
    code = (state_code or "").strip().upper()
    if code:
        if code == "FCT":
            code = "FC"
        by_code = NigerianState.objects.filter(code=code).first()
        if by_code is not None:
            return by_code

    cleaned = _normalize_label(hint)
    if not cleaned:
        return None
    if "federal capital" in cleaned or "abuja" in cleaned or cleaned == "fct":
        return NigerianState.objects.filter(code="FC").first()
    for state in NigerianState.objects.all():
        norm = _normalize_label(state.name)
        if norm == cleaned or cleaned in norm or norm in cleaned:
            return state
    return None


def match_nigerian_lga(state: NigerianState, hints: list[str]) -> NigerianLGA | None:
    lgas = list(NigerianLGA.objects.filter(state=state))
    expanded_hints: list[str] = []
    for raw in hints:
        if not raw:
            continue
        expanded_hints.append(raw)
        expanded_hints.extend(_split_alt_names(raw))

    normalized_hints = []
    for h in expanded_hints:
        norm = _normalize_label(h)
        if norm and norm not in normalized_hints:
            normalized_hints.append(norm)
        raw_lower = re.sub(r"[^a-z0-9]+", " ", (h or "").strip().lower()).strip()
        if raw_lower and raw_lower not in normalized_hints:
            normalized_hints.append(raw_lower)

    if not normalized_hints:
        return None

    # Special FCT AMAC handling (GRID3 uses "Municipal Area Council", INEC/app uses "Abuja Municipal (AMAC)")
    if state.code == "FC":
        for hint in normalized_hints:
            if any(tok in hint for tok in ("amac", "municipal", "abuja municipal")):
                for lga in lgas:
                    if "municipal" in lga.name.lower() or "amac" in lga.name.lower():
                        return lga

    # 1. Exact normalized match
    for hint in normalized_hints:
        hint_compact = _compact_label(hint)
        for lga in lgas:
            if _normalize_label(lga.name) == hint or (
                hint_compact and _compact_label(lga.name) == hint_compact
            ):
                return lga

    # 2. Substring match fallback
    for hint in normalized_hints:
        if len(hint) < 3:
            continue
        for lga in lgas:
            norm = _normalize_label(lga.name)
            if norm and (hint in norm or norm in hint):
                return lga
    return None


def _ward_source_priority(ward: NigerianWard) -> int:
    order = {
        NigerianWard.DataSource.INEC: 0,
        NigerianWard.DataSource.GRID3: 1,
        NigerianWard.DataSource.SEED: 2,
        NigerianWard.DataSource.COMMUNITY: 3,
    }
    return order.get(ward.data_source, 4)


def match_nigerian_ward(
    lga: NigerianLGA,
    hints: list[str],
    *,
    official_only: bool = False,
) -> NigerianWard | None:
    """
    Match a NigerianWard inside an LGA using normalized names, compact forms (e.g. Oko-Erin == Okoerin),
    slash-delimited compound names, and GRID3 alt_names — always preferring official INEC/GRID3 records.
    """
    qs = NigerianWard.objects.filter(lga=lga)
    if official_only:
        qs = qs.filter(data_source__in=_OFFICIAL_SOURCES)
    wards = sorted(list(qs), key=lambda w: (_ward_source_priority(w), w.name.lower()))
    if not wards:
        return None

    expanded: list[str] = []
    for h in hints:
        if not h:
            continue
        expanded.append(h)
        expanded.extend(_split_alt_names(h))

    norm_hints = []
    compact_hints = []
    for item in expanded:
        n = _normalize_label(item)
        c = _compact_label(item)
        if n and n not in norm_hints:
            norm_hints.append(n)
        if c and c not in compact_hints:
            compact_hints.append(c)

    if not norm_hints:
        return None

    def _ward_keys(w: NigerianWard) -> tuple[set[str], set[str]]:
        names = [w.name, *_split_alt_names(w.alt_names)]
        # Also split slash-separated aliases like "Opebi / Allen" or "Ojuekun/Zarumi"
        parts: list[str] = []
        for nm in names:
            parts.append(nm)
            if "/" in nm:
                parts.extend([p.strip() for p in nm.split("/") if p.strip()])
        norms = {_normalize_label(p) for p in parts if _normalize_label(p)}
        compacts = {_compact_label(p) for p in parts if _compact_label(p)}
        return norms, compacts

    indexed = [(w, *_ward_keys(w)) for w in wards]

    # 1. Exact normalized or compact match against primary name or alt_names
    for hint in norm_hints:
        h_comp = _compact_label(hint)
        for ward, w_norms, w_compacts in indexed:
            if hint in w_norms or (h_comp and h_comp in w_compacts):
                return ward

    # 2. Sub-part / slash-segment token match (e.g. GRID3 "Oju-Ekun" <-> INEC "Ojuekun/Zarumi")
    hint_segments: list[str] = []
    for item in expanded:
        if "/" in item:
            for seg in item.split("/"):
                c = _compact_label(seg)
                if len(c) >= 4 and c not in hint_segments:
                    hint_segments.append(c)
    for seg in [*compact_hints, *hint_segments]:
        if len(seg) < 4:
            continue
        for ward, _w_norms, w_compacts in indexed:
            if any(seg == wc or (len(wc) >= 4 and (seg in wc or wc in seg)) for wc in w_compacts):
                return ward

    return None


def _http_get_json(url: str, *, timeout: float, user_agent: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def lookup_grid3_ward(latitude: Decimal, longitude: Decimal) -> dict | None:
    """
    Authoritative Point-in-Polygon lookup against official GRID3 Nigeria Operational Wards v4.0
    (CIESIN / Columbia University / NPHCDA — free ArcGIS FeatureServer, no API key required).
    Returns attribute dict with state, statecode, lga, lga_alt_names, ward, ward_alt_names, or None.
    """
    if not getattr(settings, "LOCATION_EXTERNAL_LOOKUP_ENABLED", True):
        return None
    base_url = getattr(settings, "GRID3_WARD_API_URL", "").strip()
    if not base_url:
        return None

    cache_key = (round(float(latitude), 4), round(float(longitude), 4))
    now = time.monotonic()
    cached = _grid3_point_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    params = urllib.parse.urlencode(
        {
            "geometry": f"{longitude},{latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "state,statecode,lga,lga_alt_names,ward,ward_alt_names",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    timeout = float(getattr(settings, "GRID3_API_TIMEOUT_SECONDS", 4.0))
    data = _http_get_json(
        f"{base_url}?{params}",
        timeout=timeout,
        user_agent="ArtisanOS-Nigeria/2.0 (grid3-ward-lookup)",
    )
    if not data or "error" in data:
        return None

    features = data.get("features") or []
    result = features[0].get("attributes") if features and isinstance(features[0], dict) else None

    if len(_grid3_point_cache) >= _GRID3_CACHE_MAX_SIZE:
        _grid3_point_cache.clear()
    _grid3_point_cache[cache_key] = (now + _GRID3_CACHE_TTL_SECONDS, result)
    return result


def lookup_grid3_nearby_wards(
    latitude: Decimal,
    longitude: Decimal,
    radius_meters: int = 800,
) -> list[dict]:
    """
    Query GRID3 Nigeria Operational Wards v4.0 within a circular GPS uncertainty buffer
    so users on Wi-Fi/cell-tower geolocation near a ward boundary can switch in 1 tap.
    """
    if not getattr(settings, "LOCATION_EXTERNAL_LOOKUP_ENABLED", True):
        return []
    base_url = getattr(settings, "GRID3_WARD_API_URL", "").strip()
    if not base_url:
        return []

    clamped_radius = max(250, min(int(radius_meters), 2000))
    cache_key = (round(float(latitude), 3), round(float(longitude), 3), clamped_radius)
    now = time.monotonic()
    cached = _grid3_nearby_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]

    params = urllib.parse.urlencode(
        {
            "geometry": f"{longitude},{latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "distance": str(clamped_radius),
            "units": "esriSRUnit_Meter",
            "outFields": "state,statecode,lga,lga_alt_names,ward,ward_alt_names",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    timeout = float(getattr(settings, "GRID3_API_TIMEOUT_SECONDS", 4.0))
    data = _http_get_json(
        f"{base_url}?{params}",
        timeout=timeout,
        user_agent="ArtisanOS-Nigeria/2.0 (grid3-ward-buffer)",
    )
    if not data or "error" in data:
        return []

    attrs_list = [
        f["attributes"]
        for f in (data.get("features") or [])
        if isinstance(f, dict) and isinstance(f.get("attributes"), dict)
    ]
    if len(_grid3_nearby_cache) >= _GRID3_CACHE_MAX_SIZE:
        _grid3_nearby_cache.clear()
    _grid3_nearby_cache[cache_key] = (now + _GRID3_CACHE_TTL_SECONDS, attrs_list)
    return attrs_list


def reverse_geocode_google_maps(latitude: Decimal, longitude: Decimal) -> dict | None:
    """
    Optional Google Maps Geocoding API reverse lookup (used when GOOGLE_MAPS_API_KEY is configured).
    Note: Google Maps does NOT return Nigerian INEC Electoral Wards, so this is used strictly for
    accurate street/landmark naming and coarse State/LGA fallback.
    """
    if not getattr(settings, "LOCATION_EXTERNAL_LOOKUP_ENABLED", True):
        return None
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return None

    params = urllib.parse.urlencode(
        {
            "latlng": f"{latitude},{longitude}",
            "language": "en",
            "key": api_key,
        }
    )
    timeout = float(getattr(settings, "LOCATION_GEOCODE_TIMEOUT_SECONDS", 3.0))
    data = _http_get_json(
        f"https://maps.googleapis.com/maps/api/geocode/json?{params}",
        timeout=timeout,
        user_agent="ArtisanOS-Nigeria/2.0",
    )
    if not data or data.get("status") != "OK":
        return None

    results = data.get("results") or []
    if not results:
        return None

    state_hint = ""
    lga_hints: list[str] = []
    ward_hints: list[str] = []
    landmark_parts: list[str] = []

    for comp in results[0].get("address_components") or []:
        types = set(comp.get("types") or [])
        long_name = (comp.get("long_name") or "").strip()
        if not long_name:
            continue
        if "administrative_area_level_1" in types and not state_hint:
            state_hint = long_name
        if "administrative_area_level_2" in types:
            lga_hints.append(long_name)
        if "locality" in types:
            lga_hints.append(long_name)
        if types & {"sublocality", "sublocality_level_1", "neighborhood"}:
            ward_hints.append(long_name)
            landmark_parts.append(long_name)
        if types & {"route", "point_of_interest", "premise"}:
            landmark_parts.insert(0, long_name)

    dedup_landmark = ", ".join(dict.fromkeys(p for p in landmark_parts if p))[:220]
    if not dedup_landmark:
        dedup_landmark = (results[0].get("formatted_address") or "")[:220]

    return {
        "provider": "google_maps",
        "state": state_hint,
        "lga_hints": lga_hints,
        "ward_hints": ward_hints,
        "landmark": dedup_landmark,
    }


def reverse_geocode_nominatim(latitude: Decimal, longitude: Decimal) -> dict | None:
    """
    Best-effort OpenStreetMap Nominatim reverse lookup for Nigerian coordinates.
    Returns raw parsed dict or None if offline/unreachable.
    Used strictly for street/landmark context and coarse State/LGA fallback — NEVER to invent Wards.
    """
    if not getattr(settings, "LOCATION_EXTERNAL_LOOKUP_ENABLED", True):
        return None
    base_url = getattr(
        settings,
        "NOMINATIM_API_URL",
        "https://nominatim.openstreetmap.org/reverse",
    ).strip()
    params = urllib.parse.urlencode(
        {
            "format": "jsonv2",
            "lat": str(latitude),
            "lon": str(longitude),
            "addressdetails": "1",
            "zoom": "16",
        }
    )
    timeout = float(getattr(settings, "LOCATION_GEOCODE_TIMEOUT_SECONDS", 3.0))
    return _http_get_json(
        f"{base_url}?{params}",
        timeout=timeout,
        user_agent="ArtisanOS-Nigeria/2.0 (hyperlocal-artisan-directory)",
    )


def _reverse_geocode_context(latitude: Decimal, longitude: Decimal) -> dict | None:
    """Try Google Maps Geocoding API (if key configured), then free Nominatim."""
    google = reverse_geocode_google_maps(latitude, longitude)
    if google is not None:
        return google

    nom = reverse_geocode_nominatim(latitude, longitude)
    if nom and isinstance(nom.get("address"), dict):
        addr = nom["address"]
        landmark_parts = [
            addr.get("road", ""),
            addr.get("neighbourhood", ""),
            addr.get("suburb", ""),
            addr.get("quarter", ""),
        ]
        landmark = ", ".join(dict.fromkeys(p.strip() for p in landmark_parts if p and p.strip()))[:220]
        return {
            "provider": "nominatim",
            "state": addr.get("state") or "",
            "lga_hints": [
                addr.get("county", ""),
                addr.get("city_district", ""),
                addr.get("municipality", ""),
                addr.get("city", ""),
                addr.get("town", ""),
            ],
            "ward_hints": [
                addr.get("suburb", ""),
                addr.get("quarter", ""),
                addr.get("neighbourhood", ""),
            ],
            "landmark": landmark,
        }
    return None


@transaction.atomic
def _resolve_or_upsert_grid3_ward(attrs: dict) -> tuple[NigerianState | None, NigerianLGA | None, NigerianWard | None]:
    """Resolve a GRID3 ward feature to canonical (State, LGA, Ward) records without fabricating fake PUs."""
    state = match_nigerian_state(attrs.get("state", ""), state_code=attrs.get("statecode", ""))
    if state is None:
        return None, None, None

    lga_hints = [attrs.get("lga", ""), attrs.get("lga_alt_names", "")]
    lga = match_nigerian_lga(state, lga_hints)
    if lga is None:
        return state, None, None

    raw_ward = (attrs.get("ward") or "").strip()[:150]
    raw_alt = (attrs.get("ward_alt_names") or "").strip()[:300]
    if not raw_ward:
        return state, lga, None

    ward = match_nigerian_ward(lga, [raw_ward, raw_alt])
    if ward is not None:
        # Enrich existing INEC ward with GRID3 alt_names if helpful
        if raw_alt and not ward.alt_names:
            ward.alt_names = raw_alt
            ward.save(update_fields=["alt_names", "updated_at"])
        return state, lga, ward

    # Official GRID3 ward not yet in DB (e.g., before full INEC CSV sync) — register official GRID3 ward cleanly
    existing_count = NigerianWard.objects.filter(lga=lga).count()
    ward, _ = NigerianWard.objects.get_or_create(
        lga=lga,
        name=raw_ward,
        defaults={
            "code": f"{existing_count + 1:02d}",
            "alt_names": raw_alt,
            "data_source": NigerianWard.DataSource.GRID3,
        },
    )
    return state, lga, ward


def _find_nearest_polling_unit(
    latitude: Decimal,
    longitude: Decimal,
    *,
    ward: NigerianWard | None = None,
) -> tuple[PollingUnit | None, float | None]:
    """
    Find the closest geolocated PollingUnit.
    - When `ward` is provided, strictly scopes to PollingUnits INSIDE that exact Ward.
    - Otherwise uses progressive tight bounding boxes (0.015 deg -> 0.55 deg) so dense cities
      never drop nearby PUs to an unordered LIMIT 500.
    """
    base_qs = PollingUnit.objects.select_related("ward", "ward__lga", "ward__lga__state").filter(
        latitude__isnull=False,
        longitude__isnull=False,
    )

    def _pick_best(candidates: list[PollingUnit]) -> tuple[PollingUnit | None, float | None]:
        best_any: PollingUnit | None = None
        best_any_km: float | None = None
        best_official: PollingUnit | None = None
        best_official_km: float | None = None
        for cand in candidates:
            dist = haversine_km(latitude, longitude, cand.latitude, cand.longitude)
            if dist is None:
                continue
            if best_any_km is None or dist < best_any_km:
                best_any_km = dist
                best_any = cand
            is_legacy_auto = "/AUTO/" in (cand.pu_code or "")
            if not is_legacy_auto and (best_official_km is None or dist < best_official_km):
                best_official_km = dist
                best_official = cand
        # Prefer official PU if it is within 0.35 km of a legacy auto-generated PU
        if (
            best_official is not None
            and best_official_km is not None
            and (best_any_km is None or best_official_km <= best_any_km + 0.35)
        ):
            return best_official, best_official_km
        return best_any, best_any_km

    if ward is not None:
        candidates = list(base_qs.filter(ward=ward)[:600])
        return _pick_best(candidates)

    for delta_deg in (Decimal("0.015"), Decimal("0.05"), Decimal("0.15"), Decimal("0.55")):
        candidates = list(
            base_qs.filter(
                latitude__gte=latitude - delta_deg,
                latitude__lte=latitude + delta_deg,
                longitude__gte=longitude - delta_deg,
                longitude__lte=longitude + delta_deg,
            )[:600]
        )
        if candidates:
            return _pick_best(candidates)

    return None, None


def _get_candidate_polling_units(
    ward: NigerianWard | None,
    *,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    limit: int = 8,
) -> list[PollingUnit]:
    """Return top official Polling Units inside the confirmed Ward (nearest geolocated first)."""
    if ward is None:
        return []
    pus = list(
        PollingUnit.objects.select_related("ward", "ward__lga", "ward__lga__state")
        .filter(ward=ward)
        .order_by("pu_code", "name")[:200]
    )
    official_pus = [p for p in pus if "/AUTO/" not in (p.pu_code or "")]
    pool = official_pus or pus

    if latitude is not None and longitude is not None:
        def _sort_key(pu: PollingUnit) -> tuple[int, float, str]:
            if pu.latitude is not None and pu.longitude is not None:
                d = haversine_km(latitude, longitude, pu.latitude, pu.longitude)
                if d is not None:
                    return (0, d, pu.name.lower())
            return (1, 99999.0, pu.name.lower())

        pool.sort(key=_sort_key)

    return pool[:limit]


@transaction.atomic
def ensure_ward_and_polling_unit(
    *,
    lga: NigerianLGA,
    ward_name: str,
    polling_unit_name: str = "",
    landmark: str = "",
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    data_source: str = NigerianWard.DataSource.COMMUNITY,
    alt_names: str = "",
) -> tuple[NigerianWard, PollingUnit | None]:
    """
    Find or explicitly register a NigerianWard (and optional PollingUnit) under any of Nigeria's 774 LGAs.
    Always matches existing official INEC/GRID3 wards first before creating a new community entry.
    """
    cleaned_ward = ward_name.strip()[:150]
    if not cleaned_ward:
        cleaned_ward = f"{lga.name} Central"

    ward = NigerianWard.objects.filter(lga=lga, name__iexact=cleaned_ward).first()
    if ward is None:
        ward = match_nigerian_ward(lga, [cleaned_ward])
    if ward is None:
        existing_count = NigerianWard.objects.filter(lga=lga).count()
        ward = NigerianWard.objects.create(
            lga=lga,
            name=cleaned_ward,
            code=f"{existing_count + 1:02d}",
            alt_names=alt_names[:300],
            data_source=data_source,
        )

    pu = None
    cleaned_pu = polling_unit_name.strip()[:220]
    if cleaned_pu:
        pu = PollingUnit.objects.filter(ward=ward, name__iexact=cleaned_pu).first()
        if not pu:
            state_code = lga.state.code
            pu_code = f"{state_code}/COMM/{uuid.uuid4().hex[:6].upper()}"
            pu_source = (
                PollingUnit.DataSource.COMMUNITY
                if data_source == NigerianWard.DataSource.COMMUNITY
                else data_source
            )
            pu = PollingUnit.objects.create(
                ward=ward,
                name=cleaned_pu,
                pu_code=pu_code,
                landmark=(landmark or f"{ward.name}, {lga.name}").strip()[:220],
                latitude=latitude,
                longitude=longitude,
                data_source=pu_source,
            )
        elif latitude is not None and longitude is not None and pu.latitude is None:
            pu.latitude = latitude
            pu.longitude = longitude
            pu.save(update_fields=["latitude", "longitude", "updated_at"])

    return ward, pu


def _build_detection_result(
    *,
    state: NigerianState | None = None,
    lga: NigerianLGA | None = None,
    ward: NigerianWard | None = None,
    polling_unit: PollingUnit | None = None,
    landmark: str = "",
    match_source: str = "unmatched",
    provider: str = "none",
    confidence: str = "low",
    accuracy_meters: float | None = None,
    distance_km: float | None = None,
    nearby_wards: list[NigerianWard] | None = None,
    candidate_polling_units: list[PollingUnit] | None = None,
    warning: str = "",
) -> dict:
    return {
        "state": state,
        "lga": lga,
        "ward": ward,
        "polling_unit": polling_unit,
        "landmark": landmark,
        "match_source": match_source,
        "provider": provider,
        "confidence": confidence,
        "accuracy_meters": accuracy_meters,
        "distance_km": distance_km,
        "nearby_wards": nearby_wards or [],
        "candidate_polling_units": candidate_polling_units or [],
        "warning": warning,
    }


@transaction.atomic
def detect_nigerian_location(
    *,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    accuracy_meters: float | None = None,
    state_name: str = "",
    lga_name: str = "",
    ward_name: str = "",
    polling_unit_name: str = "",
    landmark: str = "",
    allow_reverse_geocode: bool = True,
) -> dict:
    """
    Standardized Nigerian State -> LGA -> Electoral Ward -> Polling Unit detector.

    Resolution order:
    1. Explicit user-supplied State + LGA + Ward hints (manual mapping).
    2. Nigeria geographic bounds validation (rejects out-of-Nigeria coordinates cleanly).
    3. Authoritative GRID3 Nigeria Operational Wards v4.0 Point-in-Polygon (FREE, official CIESIN/NPHCDA
       boundaries — solves the OSM/Google limitation where neither maps Nigerian electoral wards).
       - Matches canonical INEC/GRID3 Ward (including alt_names).
       - Finds nearest geolocated Polling Unit strictly INSIDE that confirmed Ward (never cross-ward drift).
       - Returns official candidate Polling Units in that Ward + neighboring Wards within the GPS accuracy radius.
       - Optionally enriches street/landmark via Google Maps (if API key set) or Nominatim (free) WITHOUT
         ever overwriting the Ward or fabricating fake wards from town/suburb names.
    4. Offline / GRID3-unreachable fallback:
       - Tight progressive bounding-box search against local geolocated INEC Polling Units (within 2.5 km).
       - Otherwise Google Maps / Nominatim for State + LGA + landmark ONLY (never fabricating fake Wards!).
       - Final fallback: closest known Polling Unit within 50 km.
    """
    # 1. Explicit user-supplied hints (e.g. direct mapping by State/LGA/Ward name)
    if state_name and ward_name:
        state = match_nigerian_state(state_name)
        if state is not None:
            lga = match_nigerian_lga(state, [lga_name]) if lga_name else None
            if lga is None:
                lga = NigerianLGA.objects.filter(state=state).order_by("name").first()
            if lga is not None:
                ward, pu = ensure_ward_and_polling_unit(
                    lga=lga,
                    ward_name=ward_name,
                    polling_unit_name=polling_unit_name,
                    landmark=landmark,
                    latitude=latitude,
                    longitude=longitude,
                )
                return _build_detection_result(
                    state=state,
                    lga=lga,
                    ward=ward,
                    polling_unit=pu,
                    landmark=landmark or (pu.landmark if pu else ""),
                    match_source="explicit_mapped",
                    provider="explicit_input",
                    confidence="high",
                    accuracy_meters=accuracy_meters,
                    distance_km=0.0 if latitude is not None else None,
                    candidate_polling_units=_get_candidate_polling_units(
                        ward, latitude=latitude, longitude=longitude
                    ),
                )

    # 2. Validate GPS coordinates lie inside Nigeria
    has_coords = latitude is not None and longitude is not None
    if has_coords and not is_within_nigeria_bounds(latitude, longitude):
        return _build_detection_result(
            landmark=landmark,
            match_source="outside_nigeria",
            provider="bounds_check",
            confidence="low",
            accuracy_meters=accuracy_meters,
            warning=(
                "Your GPS coordinates appear to be outside Nigeria. "
                "Please select your State, LGA, and neighborhood manually below."
            ),
        )

    # 3. Primary Standard: GRID3 Nigeria Operational Wards v4.0 Point-in-Polygon
    if has_coords and allow_reverse_geocode:
        grid3_attrs = lookup_grid3_ward(latitude, longitude)
        if grid3_attrs:
            state, lga, ward = _resolve_or_upsert_grid3_ward(grid3_attrs)
            if state is not None and lga is not None and ward is not None:
                # Find nearest geolocated PU strictly INSIDE this confirmed Ward
                ward_pu, ward_pu_km = _find_nearest_polling_unit(latitude, longitude, ward=ward)
                if ward_pu_km is not None and ward_pu_km > 3.0:
                    ward_pu = None
                    ward_pu_km = None

                candidates = _get_candidate_polling_units(
                    ward, latitude=latitude, longitude=longitude
                )

                # Fetch neighboring official wards if GPS accuracy is coarse or unknown
                nearby_wards: list[NigerianWard] = []
                buffer_m = int(accuracy_meters) if accuracy_meters and accuracy_meters > 250 else 500
                if accuracy_meters is None or accuracy_meters > 150:
                    seen_ward_ids = {ward.id}
                    for nb_attrs in lookup_grid3_nearby_wards(latitude, longitude, radius_meters=buffer_m):
                        _ns, _nl, nb_ward = _resolve_or_upsert_grid3_ward(nb_attrs)
                        if nb_ward is not None and nb_ward.id not in seen_ward_ids:
                            seen_ward_ids.add(nb_ward.id)
                            nearby_wards.append(nb_ward)
                        if len(nearby_wards) >= 5:
                            break

                # Best-effort landmark enrichment (Google Maps if configured, else Nominatim)
                resolved_landmark = landmark
                if not resolved_landmark:
                    ctx = _reverse_geocode_context(latitude, longitude)
                    if ctx and ctx.get("landmark"):
                        resolved_landmark = ctx["landmark"]
                if not resolved_landmark and ward_pu and ward_pu.landmark:
                    resolved_landmark = ward_pu.landmark

                # Honest confidence & advisory warning when device GPS accuracy is coarse (desktop Wi-Fi/cell)
                if accuracy_meters is not None and accuracy_meters > 1000:
                    confidence = "low"
                    warning = (
                        f"Your device GPS accuracy is ±{int(round(accuracy_meters))}m "
                        "(common on Wi-Fi or indoor networks). Confirm your area below or switch to a nearby neighborhood."
                    )
                elif accuracy_meters is not None and accuracy_meters > 250:
                    confidence = "medium"
                    warning = (
                        f"Device GPS accuracy is ±{int(round(accuracy_meters))}m. "
                        "Pick your nearest landmark below for exact matching."
                    )
                else:
                    confidence = "high"
                    warning = (
                        ""
                        if ward_pu is not None
                        else f"Confirmed {ward.name} area. Select your nearest spot below to narrow results."
                    )

                return _build_detection_result(
                    state=state,
                    lga=lga,
                    ward=ward,
                    polling_unit=ward_pu,
                    landmark=resolved_landmark,
                    match_source="grid3_ward_with_nearest_pu" if ward_pu else "grid3_ward_polygon",
                    provider="grid3_v4",
                    confidence=confidence,
                    accuracy_meters=accuracy_meters,
                    distance_km=ward_pu_km,
                    nearby_wards=nearby_wards,
                    candidate_polling_units=candidates,
                    warning=warning,
                )

    # 4. Offline / GRID3-unreachable fallback: local geolocated INEC Polling Unit search
    nearest_pu: PollingUnit | None = None
    nearest_km: float | None = None
    if has_coords:
        nearest_pu, nearest_km = _find_nearest_polling_unit(latitude, longitude)
        if nearest_pu is not None and nearest_km is not None and nearest_km <= 2.5 and not ward_name:
            confidence = "high" if nearest_km <= 0.5 else "medium"
            warning = (
                ""
                if nearest_km <= 0.5
                else (
                    f"Matched nearest area point ({nearest_km:.1f} km away). "
                    "Verify your neighborhood below."
                )
            )
            return _build_detection_result(
                state=nearest_pu.ward.lga.state,
                lga=nearest_pu.ward.lga,
                ward=nearest_pu.ward,
                polling_unit=nearest_pu,
                landmark=nearest_pu.landmark or landmark,
                match_source="exact_nearby_pu",
                provider="local_inec",
                confidence=confidence,
                accuracy_meters=accuracy_meters,
                distance_km=nearest_km,
                candidate_polling_units=_get_candidate_polling_units(
                    nearest_pu.ward, latitude=latitude, longitude=longitude
                ),
                warning=warning,
            )

    # 5. Google Maps / Nominatim fallback — resolves State + LGA + landmark ONLY
    #    CRITICAL: NEVER fabricates fake Wards or Polling Units from OSM town/suburb names!
    geo_ctx: dict | None = None
    if allow_reverse_geocode and has_coords and not (state_name and lga_name):
        geo_ctx = _reverse_geocode_context(latitude, longitude)

    resolved_state_hint = state_name or (geo_ctx.get("state", "") if geo_ctx else "")
    lga_hints = [lga_name] + (geo_ctx.get("lga_hints", []) if geo_ctx else [])
    ward_hints = [ward_name] + (geo_ctx.get("ward_hints", []) if geo_ctx else [])
    resolved_landmark = landmark or (geo_ctx.get("landmark", "") if geo_ctx else "")
    geo_provider = (geo_ctx.get("provider") if geo_ctx else "explicit_input") or "none"

    state = match_nigerian_state(resolved_state_hint)
    if state is not None:
        lga = match_nigerian_lga(state, lga_hints)
        if lga is not None:
            # Match ONLY against already-known official Wards in this LGA — never invent one from OSM!
            matched_ward = match_nigerian_ward(lga, ward_hints, official_only=True)
            candidates = _get_candidate_polling_units(
                matched_ward, latitude=latitude, longitude=longitude
            )
            if matched_ward is not None:
                return _build_detection_result(
                    state=state,
                    lga=lga,
                    ward=matched_ward,
                    polling_unit=None,
                    landmark=resolved_landmark,
                    match_source="reverse_geocode_matched_ward",
                    provider=geo_provider,
                    confidence="medium",
                    accuracy_meters=accuracy_meters,
                    candidate_polling_units=candidates,
                    warning=f"Matched {matched_ward.name} in {lga.name}. Select your nearest spot below.",
                )
            return _build_detection_result(
                state=state,
                lga=lga,
                ward=None,
                polling_unit=None,
                landmark=resolved_landmark,
                match_source="reverse_geocode_lga_only",
                provider=geo_provider,
                confidence="low",
                accuracy_meters=accuracy_meters,
                warning=(
                    f"Detected {lga.name}, {state.name}. "
                    "Please pick your neighborhood below for closer matches."
                ),
            )

    # 6. Last-resort offline fallback: closest known Polling Unit within 50 km
    if nearest_pu is not None and nearest_km is not None and nearest_km <= 50.0:
        return _build_detection_result(
            state=nearest_pu.ward.lga.state,
            lga=nearest_pu.ward.lga,
            ward=nearest_pu.ward,
            polling_unit=nearest_pu,
            landmark=nearest_pu.landmark or landmark,
            match_source="nearest_known_pu",
            provider="local_inec",
            confidence="low",
            accuracy_meters=accuracy_meters,
            distance_km=nearest_km,
            candidate_polling_units=_get_candidate_polling_units(
                nearest_pu.ward, latitude=latitude, longitude=longitude
            ),
            warning=(
                f"Approximate location ({nearest_km:.1f} km from nearest known spot). "
                "Please confirm your neighborhood below."
            ),
        )

    return _build_detection_result(
        landmark=landmark,
        match_source="unmatched",
        provider="none",
        confidence="low",
        accuracy_meters=accuracy_meters,
        warning="Could not auto-detect your location. Please choose your State, LGA, and area below.",
    )


@transaction.atomic
def cleanup_unofficial_locations(*, dry_run: bool = True) -> dict[str, int]:
    """
    Safely remove legacy auto-generated `/AUTO/` Polling Units and orphaned non-official Wards
    (such as OSM town names like 'Oja Tutun, Oko Erin, Nigeria') that are not referenced by any
    User, Organization, or StorefrontInquiry.
    """
    from accounts.models import User
    from catalog.models import StorefrontInquiry
    from organizations.models import Organization

    used_pu_ids = (
        set(User.objects.exclude(polling_unit_id__isnull=True).values_list("polling_unit_id", flat=True))
        | set(Organization.objects.exclude(polling_unit_id__isnull=True).values_list("polling_unit_id", flat=True))
        | set(
            StorefrontInquiry.objects.exclude(customer_polling_unit_id__isnull=True).values_list(
                "customer_polling_unit_id", flat=True
            )
        )
    )
    used_ward_ids = (
        set(User.objects.exclude(ward_id__isnull=True).values_list("ward_id", flat=True))
        | set(Organization.objects.exclude(ward_id__isnull=True).values_list("ward_id", flat=True))
        | set(Organization.service_wards.through.objects.values_list("nigerianward_id", flat=True))
        | set(
            StorefrontInquiry.objects.exclude(customer_ward_id__isnull=True).values_list(
                "customer_ward_id", flat=True
            )
        )
    )

    legacy_auto_pus = PollingUnit.objects.filter(pu_code__contains="/AUTO/")
    removable_pus = legacy_auto_pus.exclude(id__in=used_pu_ids)
    removable_pu_count = removable_pus.count()
    protected_pu_count = legacy_auto_pus.filter(id__in=used_pu_ids).count()

    candidate_ward_ids = set(removable_pus.values_list("ward_id", flat=True))
    if not dry_run and removable_pu_count:
        removable_pus.delete()

    # Check if any community/legacy ward that only held removed `/AUTO/` PUs is now empty & unreferenced
    removable_ward_qs = NigerianWard.objects.filter(id__in=candidate_ward_ids).exclude(id__in=used_ward_ids)
    if dry_run:
        # Exclude wards that still have non-AUTO polling units
        wards_with_official_pus = set(
            PollingUnit.objects.filter(ward_id__in=candidate_ward_ids)
            .exclude(pu_code__contains="/AUTO/")
            .values_list("ward_id", flat=True)
        )
        removable_ward_qs = removable_ward_qs.exclude(id__in=wards_with_official_pus)
    else:
        wards_with_remaining_pus = set(
            PollingUnit.objects.filter(ward_id__in=candidate_ward_ids).values_list("ward_id", flat=True)
        )
        removable_ward_qs = removable_ward_qs.exclude(id__in=wards_with_remaining_pus)

    removable_ward_count = removable_ward_qs.count()
    if not dry_run and removable_ward_count:
        removable_ward_qs.delete()

    return {
        "dry_run": int(dry_run),
        "legacy_auto_pus_removed": removable_pu_count,
        "legacy_auto_pus_protected": protected_pu_count,
        "orphaned_wards_removed": removable_ward_count,
    }
