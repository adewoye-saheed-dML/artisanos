"""
Production-grade bulk importer for Nigeria's complete official INEC geographic dataset:
36 States + FCT Abuja (37), 774 LGAs, 8,809 Electoral Wards, and 176,846 Polling Units
with optional GPS coordinate enrichment.
"""

import csv
import io
import re
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from .seed import seed_nigeria_locations
from .services import is_within_nigeria_bounds

# Authoritative open-source INEC dataset URLs (complete 176,846 polling units + geo coordinates)
DEFAULT_INEC_COMPLETE_CSV_URLS = [
    "https://raw.githubusercontent.com/Emeka-Onwuepe/Polling_Units_in_Nigeria/main/Nigeria_polling_units.csv",
    "https://raw.githubusercontent.com/Emeka-Onwuepe/Polling_Units_in_Nigeria/master/Nigeria_polling_units.csv",
]

DEFAULT_INEC_GEO_CSV_URLS = [
    "https://raw.githubusercontent.com/mykeels/inec-polling-units/master/polling-units.csv",
    "https://raw.githubusercontent.com/mykeels/inec-polling-units/main/polling-units.csv",
]

STATE_ALIASES: dict[str, str] = {
    "fct": "FC",
    "f c t": "FC",
    "fct abuja": "FC",
    "abuja": "FC",
    "federal capital territory": "FC",
    "akwa ibom": "AK",
    "akwaibom": "AK",
    "cross river": "CR",
    "crossriver": "CR",
    "nassarawa": "NA",
    "nasarawa": "NA",
    "plateu": "PL",
    "plateau": "PL",
}


def _norm_key(text: str) -> str:
    cleaned = re.sub(r"\b(state|local government area|lga|area council)\b", "", (text or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def _clean_display_name(raw: str) -> str:
    """Turn all-caps INEC strings like 'OPEN SPACE BY ALLEN AVE' into clean readable Title Case."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return ""
    if text.isupper() or text.islower():
        words = text.title().split(" ")
        keep_upper = {"LGA", "FCT", "GRA", "PH", "VI", "LUTH", "UNILAG", "UNIPORT", "UI", "ABU", "NYSC", "INEC", "PVC", "II", "III", "IV", "I"}
        return " ".join(w.upper() if w.upper() in keep_upper else w for w in words)
    return text


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned or cleaned.lower() in {"nan", "null", "none", "n/a"}:
        return None
    try:
        val = Decimal(cleaned)
        if val == Decimal("0"):
            return None
        return val.quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        return None


def _pick_col(row: dict[str, str], candidates: list[str]) -> str:
    for key in candidates:
        if key in row and row[key] is not None and str(row[key]).strip():
            return str(row[key]).strip()
    return ""


def download_csv_text(urls: list[str], timeout: int = 60) -> tuple[str, str]:
    """Download the first reachable CSV URL from a fallback list."""
    last_error = None
    for url in urls:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "ArtisanOS-Nigeria-INEC-Sync/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    raw_bytes = resp.read()
                    return raw_bytes.decode("utf-8-sig", errors="replace"), url
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            continue
    raise RuntimeError(f"Could not download INEC CSV from {urls}: {last_error}")


def import_inec_csv_stream(
    text_stream: io.TextIOBase,
    *,
    enrich_coordinates_only: bool = False,
    progress_callback=None,
) -> dict[str, int]:
    """
    High-speed batched importer for official INEC CSV files (176,846+ rows).
    Handles both Emeka-Onwuepe (176,846 complete PUs) and mykeels (geolocated PUs) CSV formats.
    """
    # Guarantee all 37 canonical states & 774 LGAs exist first
    seed_nigeria_locations()

    states_by_code: dict[str, NigerianState] = {s.code: s for s in NigerianState.objects.all()}
    states_by_norm: dict[str, NigerianState] = {_norm_key(s.name): s for s in states_by_code.values()}
    for alias, code in STATE_ALIASES.items():
        if code in states_by_code:
            states_by_norm[alias] = states_by_code[code]

    # Map existing LGAs by (state_id, norm_lga_name)
    lgas_by_key: dict[tuple, NigerianLGA] = {}
    for lga in NigerianLGA.objects.select_related("state").all():
        lgas_by_key[(lga.state_id, _norm_key(lga.name))] = lga
        # Helpful AMAC alias
        if lga.state.code == "FC" and "abuja municipal" in lga.name.lower():
            lgas_by_key[(lga.state_id, "amac")] = lga
            lgas_by_key[(lga.state_id, "municipal")] = lga
            lgas_by_key[(lga.state_id, "abuja municipal")] = lga

    # Map existing Wards by (lga_id, norm_ward_name)
    wards_by_key: dict[tuple, NigerianWard] = {
        (w.lga_id, _norm_key(w.name)): w for w in NigerianWard.objects.all()
    }

    # Map existing Polling Units by pu_code and by (ward_id, norm_pu_name)
    existing_pu_codes: set[str] = set()
    pus_by_ward_name: dict[tuple, PollingUnit] = {}
    for pu in PollingUnit.objects.only("id", "ward_id", "pu_code", "name", "latitude", "longitude"):
        existing_pu_codes.add(pu.pu_code)
        pus_by_ward_name[(pu.ward_id, _norm_key(pu.name))] = pu

    reader = csv.DictReader(text_stream)
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row.")

    # Normalize header lookup per row (case-insensitive)
    parsed_rows: list[dict] = []
    new_lga_specs: dict[tuple, tuple[NigerianState, str, str]] = {}
    new_ward_specs: dict[tuple, tuple[tuple, str, str]] = {}

    rows_read = 0
    rows_skipped = 0

    for raw_row in reader:
        rows_read += 1
        row = {(k or "").strip().lower(): (v or "") for k, v in raw_row.items()}

        state_raw = _pick_col(row, ["state", "state_name", "statename"])
        lga_raw = _pick_col(row, ["lg", "lga", "lga_name", "local_government", "local_government_name"])
        ward_raw = _pick_col(row, ["ward", "ward_name", "registration_area", "ra"])
        pu_name_raw = _pick_col(
            row,
            ["location", "name", "pu_name", "polling_unit", "polling_unit_name", "delimitation_name"],
        )
        pu_code_raw = _pick_col(row, ["code", "delimitation", "pu_delimitation", "full_code"])
        pu_seq_raw = _pick_col(row, ["pu_code", "unit_code"])
        ward_code_raw = _pick_col(row, ["ward_code", "ra_code"])
        lga_code_raw = _pick_col(row, ["lg_code", "lga_code"])
        lat = _parse_decimal(_pick_col(row, ["latitude", "location.latitude", "lat"]))
        lng = _parse_decimal(_pick_col(row, ["longitude", "location.longitude", "lng", "lon"]))
        if lat is not None and lng is not None and not is_within_nigeria_bounds(lat, lng):
            # Reject bad/mis-geocoded coordinates outside Nigeria (common in crowdsourced CSVs)
            lat = None
            lng = None

        state = states_by_norm.get(_norm_key(state_raw))
        if not state or not lga_raw or not ward_raw or not pu_name_raw:
            rows_skipped += 1
            continue

        lga_norm = _norm_key(lga_raw)
        lga_key = (state.id, lga_norm)
        if lga_key not in lgas_by_key and lga_key not in new_lga_specs:
            # Fuzzy fallback against canonical 774 LGAs in the same state before creating a new LGA
            matched_lga = None
            for (st_id, existing_norm), existing_lga in lgas_by_key.items():
                if st_id == state.id and existing_norm and (
                    lga_norm in existing_norm or existing_norm in lga_norm
                ):
                    matched_lga = existing_lga
                    break
            if matched_lga:
                lgas_by_key[lga_key] = matched_lga
            else:
                new_lga_specs[lga_key] = (state, _clean_display_name(lga_raw)[:120], lga_code_raw[:16])

        ward_display = _clean_display_name(ward_raw)[:150]
        ward_norm = _norm_key(ward_display)
        pu_display = _clean_display_name(pu_name_raw)[:300]

        if not pu_code_raw:
            parts = [state.code, lga_code_raw or lga_norm[:4].upper(), ward_code_raw or ward_norm[:4].upper(), pu_seq_raw or str(rows_read)]
            pu_code_raw = "/".join(p for p in parts if p)
        pu_code = pu_code_raw[:48]

        parsed_rows.append(
            {
                "lga_key": lga_key,
                "ward_norm": ward_norm,
                "ward_display": ward_display,
                "ward_code": ward_code_raw[:16],
                "pu_name": pu_display,
                "pu_code": pu_code,
                "lat": lat,
                "lng": lng,
            }
        )

    # 1. Create any unmatched LGAs in bulk (rare since all 774 are pre-seeded)
    if new_lga_specs and not enrich_coordinates_only:
        NigerianLGA.objects.bulk_create(
            [
                NigerianLGA(state=st, name=name, code=code)
                for st, name, code in new_lga_specs.values()
            ],
            batch_size=500,
            ignore_conflicts=True,
        )
        for lga in NigerianLGA.objects.all():
            lgas_by_key.setdefault((lga.state_id, _norm_key(lga.name)), lga)

    # 2. Collect & bulk-create missing Wards across Nigeria (~8,809 total)
    for item in parsed_rows:
        lga = lgas_by_key.get(item["lga_key"])
        if not lga:
            continue
        w_key = (lga.id, item["ward_norm"])
        if w_key not in wards_by_key and w_key not in new_ward_specs:
            new_ward_specs[w_key] = (lga, item["ward_display"], item["ward_code"])

    wards_created = 0
    if new_ward_specs and not enrich_coordinates_only:
        ward_objs = [
            NigerianWard(
                lga=lga,
                name=name,
                code=code,
                data_source=NigerianWard.DataSource.INEC,
            )
            for lga, name, code in new_ward_specs.values()
        ]
        with transaction.atomic():
            NigerianWard.objects.bulk_create(ward_objs, batch_size=2000, ignore_conflicts=True)
        wards_created = len(ward_objs)
        for w in NigerianWard.objects.all():
            wards_by_key[(w.lga_id, _norm_key(w.name))] = w

    if progress_callback:
        progress_callback(f"Wards synced ({len(wards_by_key)} total). Preparing polling units...")

    # 3. Bulk-create Polling Units (~176,846 total) & backfill GPS coordinates
    new_pus: list[PollingUnit] = []
    coord_updates: list[PollingUnit] = []
    seen_new_codes: set[str] = set()
    updated_pu_ids: set = set()

    for item in parsed_rows:
        lga = lgas_by_key.get(item["lga_key"])
        if not lga:
            continue
        ward = wards_by_key.get((lga.id, item["ward_norm"]))
        if not ward:
            continue

        pu_norm_key = (ward.id, _norm_key(item["pu_name"]))
        existing_pu = pus_by_ward_name.get(pu_norm_key)

        if existing_pu is not None:
            if (
                item["lat"] is not None
                and item["lng"] is not None
                and existing_pu.latitude is None
                and existing_pu.id not in updated_pu_ids
            ):
                existing_pu.latitude = item["lat"]
                existing_pu.longitude = item["lng"]
                coord_updates.append(existing_pu)
                updated_pu_ids.add(existing_pu.id)
            continue

        if enrich_coordinates_only:
            continue

        code = item["pu_code"]
        if code in existing_pu_codes or code in seen_new_codes:
            # Ensure uniqueness if upstream dataset has duplicate delimitation codes
            code = f"{code[:38]}-{len(seen_new_codes) + 1}"
        seen_new_codes.add(code)

        new_pus.append(
            PollingUnit(
                ward=ward,
                name=item["pu_name"],
                pu_code=code,
                landmark=f"{ward.name}, {lga.name}",
                latitude=item["lat"],
                longitude=item["lng"],
                data_source=PollingUnit.DataSource.INEC,
            )
        )

    if new_pus:
        with transaction.atomic():
            PollingUnit.objects.bulk_create(new_pus, batch_size=5000, ignore_conflicts=True)

    if coord_updates:
        with transaction.atomic():
            PollingUnit.objects.bulk_update(coord_updates, ["latitude", "longitude"], batch_size=2000)

    return {
        "rows_read": rows_read,
        "rows_skipped": rows_skipped,
        "wards_created": wards_created,
        "polling_units_created": len(new_pus),
        "coordinates_enriched": len(coord_updates),
        "total_states": NigerianState.objects.count(),
        "total_lgas": NigerianLGA.objects.count(),
        "total_wards": NigerianWard.objects.count(),
        "total_polling_units": PollingUnit.objects.count(),
        "geolocated_polling_units": PollingUnit.objects.filter(
            latitude__isnull=False, longitude__isnull=False
        ).count(),
    }


def sync_full_inec_dataset(
    *,
    csv_path: str | Path | None = None,
    custom_url: str | None = None,
    include_geo_enrichment: bool = True,
    progress_callback=None,
) -> dict[str, int]:
    """
    Sync the full official INEC 176,846 Polling Units dataset (from local CSV or public GitHub raw CSV)
    and optionally enrich with GPS coordinates from mykeels/inec-polling-units.
    """
    if csv_path:
        if progress_callback:
            progress_callback(f"Reading local INEC CSV: {csv_path}")
        with Path(csv_path).open("r", encoding="utf-8-sig", errors="replace") as fh:
            stats = import_inec_csv_stream(fh, progress_callback=progress_callback)
    else:
        urls = [custom_url] if custom_url else DEFAULT_INEC_COMPLETE_CSV_URLS
        if progress_callback:
            progress_callback("Downloading official 176,846 INEC Polling Units CSV...")
        csv_text, resolved_url = download_csv_text(urls)
        if progress_callback:
            progress_callback(f"Downloaded from {resolved_url}. Importing into database...")
        stats = import_inec_csv_stream(io.StringIO(csv_text), progress_callback=progress_callback)

    if include_geo_enrichment and not csv_path:
        try:
            if progress_callback:
                progress_callback("Downloading GPS coordinates enrichment CSV (mykeels/inec-polling-units)...")
            geo_text, geo_url = download_csv_text(DEFAULT_INEC_GEO_CSV_URLS)
            if progress_callback:
                progress_callback(f"Enriching coordinates from {geo_url}...")
            geo_stats = import_inec_csv_stream(
                io.StringIO(geo_text),
                enrich_coordinates_only=False,
                progress_callback=progress_callback,
            )
            stats["coordinates_enriched"] = stats.get("coordinates_enriched", 0) + geo_stats.get(
                "coordinates_enriched", 0
            )
            stats["total_wards"] = geo_stats["total_wards"]
            stats["total_polling_units"] = geo_stats["total_polling_units"]
            stats["geolocated_polling_units"] = geo_stats["geolocated_polling_units"]
        except RuntimeError as exc:
            if progress_callback:
                progress_callback(f"Coordinate enrichment skipped (non-fatal): {exc}")

    return stats
