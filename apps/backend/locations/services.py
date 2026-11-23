import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal

from django.db import transaction

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from .utils import haversine_km


def _normalize_label(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"\b(state|local government area|lga|municipal area council|area council)\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def match_nigerian_state(hint: str) -> NigerianState | None:
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
    normalized_hints = [_normalize_label(h) for h in hints if h and _normalize_label(h)]
    if not normalized_hints:
        return None
    # Exact normalized match first
    for hint in normalized_hints:
        for lga in lgas:
            if _normalize_label(lga.name) == hint:
                return lga
    # Substring match fallback
    for hint in normalized_hints:
        for lga in lgas:
            norm = _normalize_label(lga.name)
            if norm and (hint in norm or norm in hint):
                return lga
    return None


def reverse_geocode_nominatim(latitude: Decimal, longitude: Decimal) -> dict | None:
    """
    Best-effort OpenStreetMap Nominatim reverse lookup for Nigerian coordinates.
    Returns parsed address dict or None if offline/unreachable.
    """
    params = urllib.parse.urlencode(
        {
            "format": "jsonv2",
            "lat": str(latitude),
            "lon": str(longitude),
            "addressdetails": "1",
            "zoom": "16",
        }
    )
    url = f"https://nominatim.openstreetmap.org/reverse?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ArtisanOS-Nigeria/1.0 (hyperlocal-artisan-directory)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


@transaction.atomic
def ensure_ward_and_polling_unit(
    *,
    lga: NigerianLGA,
    ward_name: str,
    polling_unit_name: str = "",
    landmark: str = "",
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> tuple[NigerianWard, PollingUnit | None]:
    """
    Find or organically register a NigerianWard (and optional PollingUnit) under any of Nigeria's 774 LGAs.
    As users and artisans sign up in new wards/polling units, the shared directory grows automatically.
    """
    cleaned_ward = ward_name.strip()[:150]
    if not cleaned_ward:
        cleaned_ward = f"{lga.name} Central"

    ward = NigerianWard.objects.filter(lga=lga, name__iexact=cleaned_ward).first()
    if not ward:
        existing_count = NigerianWard.objects.filter(lga=lga).count()
        ward = NigerianWard.objects.create(
            lga=lga,
            name=cleaned_ward,
            code=f"{existing_count + 1:02d}",
        )

    pu = None
    cleaned_pu = polling_unit_name.strip()[:220]
    if cleaned_pu:
        pu = PollingUnit.objects.filter(ward=ward, name__iexact=cleaned_pu).first()
        if not pu:
            state_code = lga.state.code
            pu_code = f"{state_code}/AUTO/{uuid.uuid4().hex[:6].upper()}"
            pu = PollingUnit.objects.create(
                ward=ward,
                name=cleaned_pu,
                pu_code=pu_code,
                landmark=(landmark or f"{ward.name}, {lga.name}").strip()[:220],
                latitude=latitude,
                longitude=longitude,
            )
        elif latitude is not None and longitude is not None and pu.latitude is None:
            pu.latitude = latitude
            pu.longitude = longitude
            pu.save(update_fields=["latitude", "longitude", "updated_at"])

    return ward, pu


@transaction.atomic
def detect_nigerian_location(
    *,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
    state_name: str = "",
    lga_name: str = "",
    ward_name: str = "",
    polling_unit_name: str = "",
    landmark: str = "",
    allow_reverse_geocode: bool = True,
) -> dict:
    """
    Auto-detect a user's Nigerian State -> LGA -> Ward -> Polling Unit from GPS coordinates
    and/or reverse-geocoded hints.
    1. Matches nearest known Polling Unit within 2.5 km when coordinates exist.
    2. Otherwise resolves State & LGA (out of all 37 States / 774 LGAs) via Nominatim or hints
       and auto-registers the detected Ward & Polling Unit so nearby artisans can spring up immediately.
    3. Falls back to the closest known Polling Unit in the database (within 50 km) if offline.
    """
    nearest_pu = None
    nearest_km: float | None = None

    if latitude is not None and longitude is not None:
        # Indexed bounding-box pre-filter (~15 km box first, then ~55 km fallback) for 176k+ row speed
        for delta_deg in (Decimal("0.15"), Decimal("0.55")):
            candidates = PollingUnit.objects.select_related(
                "ward", "ward__lga", "ward__lga__state"
            ).filter(
                latitude__gte=latitude - delta_deg,
                latitude__lte=latitude + delta_deg,
                longitude__gte=longitude - delta_deg,
                longitude__lte=longitude + delta_deg,
            )[:500]
            for cand in candidates:
                dist = haversine_km(latitude, longitude, cand.latitude, cand.longitude)
                if dist is not None and (nearest_km is None or dist < nearest_km):
                    nearest_km = dist
                    nearest_pu = cand
            if nearest_pu is not None:
                break

        # Direct hit on an existing Polling Unit within 2.5 km
        if nearest_pu is not None and nearest_km is not None and nearest_km <= 2.5 and not ward_name:
            return {
                "state": nearest_pu.ward.lga.state,
                "lga": nearest_pu.ward.lga,
                "ward": nearest_pu.ward,
                "polling_unit": nearest_pu,
                "landmark": nearest_pu.landmark or landmark,
                "match_source": "exact_nearby_pu",
                "distance_km": nearest_km,
            }

    # Try reverse geocoding if coordinates were supplied and hints are missing
    geo_address: dict = {}
    if allow_reverse_geocode and latitude is not None and longitude is not None and not (state_name and lga_name):
        geo = reverse_geocode_nominatim(latitude, longitude)
        if geo and isinstance(geo.get("address"), dict):
            geo_address = geo["address"]

    resolved_state_hint = state_name or geo_address.get("state") or ""
    lga_hints = [
        lga_name,
        geo_address.get("county", ""),
        geo_address.get("city_district", ""),
        geo_address.get("municipality", ""),
        geo_address.get("city", ""),
        geo_address.get("town", ""),
    ]
    resolved_ward_hint = (
        ward_name
        or geo_address.get("suburb")
        or geo_address.get("quarter")
        or geo_address.get("neighbourhood")
        or geo_address.get("town")
        or geo_address.get("village")
        or ""
    )
    resolved_pu_hint = (
        polling_unit_name
        or geo_address.get("amenity")
        or geo_address.get("road")
        or geo_address.get("neighbourhood")
        or (f"{resolved_ward_hint} Axis" if resolved_ward_hint else "")
    )
    resolved_landmark = (
        landmark
        or ", ".join(
            [
                p
                for p in [
                    geo_address.get("road", ""),
                    geo_address.get("neighbourhood", ""),
                    geo_address.get("suburb", ""),
                ]
                if p
            ]
        )
    )

    state = match_nigerian_state(resolved_state_hint)
    if state is not None:
        lga = match_nigerian_lga(state, lga_hints)
        if lga is None:
            lga = NigerianLGA.objects.filter(state=state).order_by("name").first()
        if lga is not None:
            ward, pu = ensure_ward_and_polling_unit(
                lga=lga,
                ward_name=resolved_ward_hint or f"{lga.name} Central",
                polling_unit_name=resolved_pu_hint or f"{lga.name} Main Area",
                landmark=resolved_landmark,
                latitude=latitude,
                longitude=longitude,
            )
            return {
                "state": state,
                "lga": lga,
                "ward": ward,
                "polling_unit": pu,
                "landmark": resolved_landmark,
                "match_source": "auto_detected_and_mapped",
                "distance_km": 0.0 if latitude is not None else None,
            }

    # Offline fallback: return closest known Polling Unit within 50 km
    if nearest_pu is not None and nearest_km is not None and nearest_km <= 50.0:
        return {
            "state": nearest_pu.ward.lga.state,
            "lga": nearest_pu.ward.lga,
            "ward": nearest_pu.ward,
            "polling_unit": nearest_pu,
            "landmark": nearest_pu.landmark or landmark,
            "match_source": "nearest_known_pu",
            "distance_km": nearest_km,
        }

    return {
        "state": None,
        "lga": None,
        "ward": None,
        "polling_unit": None,
        "landmark": landmark,
        "match_source": "unmatched",
        "distance_km": None,
    }
