import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import exceptions

from customers.models import ConsentRecord, Customer
from measurement_templates.models import MeasurementField, MeasurementTemplateVersion

from .models import MeasurementProfile, MeasurementRequest, MeasurementShareLink, MeasurementValue

CM_PER_INCH = Decimal("2.54")


def hash_request_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def validate_and_prepare_values(
    *,
    template_version: MeasurementTemplateVersion,
    unit_system: str,
    values_payload: list[dict],
    require_mandatory_fields: bool,
) -> list[dict]:
    """
    Validate submitted measurement values against the template version's fields.
    Performs unit-aware range validation (field bounds are stored in default_unit, typically cm).
    """
    fields_by_key: dict[str, MeasurementField] = {
        f.key: f for f in template_version.fields.all()
    }
    if not fields_by_key:
        raise exceptions.ValidationError("Selected template version has no measurement fields.")

    prepared: list[dict] = []
    seen_keys: set[str] = set()

    for item in values_payload:
        key = item.get("field_key")
        if key not in fields_by_key:
            raise exceptions.ValidationError({"values": f"Unknown field_key '{key}' for this template version."})
        if key in seen_keys:
            raise exceptions.ValidationError({"values": f"Duplicate field_key '{key}'."})
        seen_keys.add(key)

        field = fields_by_key[key]
        raw_numeric = item.get("numeric_value")
        raw_text = (item.get("text_value") or "").strip()

        if field.unit_type == MeasurementField.UnitType.TEXT:
            if not raw_text:
                continue
            prepared.append(
                {
                    "field": field,
                    "numeric_value": None,
                    "text_value": raw_text,
                    "unit": MeasurementField.DefaultUnit.NONE,
                }
            )
            continue

        if raw_numeric is None or raw_numeric == "":
            continue

        try:
            num_val = Decimal(str(raw_numeric))
        except Exception as exc:
            raise exceptions.ValidationError({"values": f"'{field.label}' must be a valid number."}) from exc

        if num_val <= 0:
            raise exceptions.ValidationError({"values": f"'{field.label}' must be greater than zero."})

        # Convert to cm for range check when field bounds are in cm and input is in inches
        value_for_bounds = num_val
        if field.default_unit == MeasurementField.DefaultUnit.CM and unit_system == MeasurementProfile.UnitSystem.IN:
            value_for_bounds = (num_val * CM_PER_INCH).quantize(Decimal("0.01"))
        elif field.default_unit == MeasurementField.DefaultUnit.IN and unit_system == MeasurementProfile.UnitSystem.CM:
            value_for_bounds = (num_val / CM_PER_INCH).quantize(Decimal("0.01"))

        if field.min_value is not None and value_for_bounds < field.min_value:
            raise exceptions.ValidationError(
                {
                    "values": (
                        f"'{field.label}' ({num_val} {unit_system}) is below the minimum allowed "
                        f"({field.min_value} {field.default_unit})."
                    )
                }
            )
        if field.max_value is not None and value_for_bounds > field.max_value:
            raise exceptions.ValidationError(
                {
                    "values": (
                        f"'{field.label}' ({num_val} {unit_system}) exceeds the maximum allowed "
                        f"({field.max_value} {field.default_unit})."
                    )
                }
            )

        unit = unit_system if field.default_unit in {"cm", "in"} else field.default_unit
        prepared.append(
            {
                "field": field,
                "numeric_value": num_val.quantize(Decimal("0.01")),
                "text_value": "",
                "unit": unit,
            }
        )

    if require_mandatory_fields:
        provided_keys = {entry["field"].key for entry in prepared}
        missing = [f.label for f in fields_by_key.values() if f.is_required and f.key not in provided_keys]
        if missing:
            raise exceptions.ValidationError(
                {"values": f"Missing required measurements: {', '.join(missing)}."}
            )

    if not prepared:
        raise exceptions.ValidationError({"values": "Provide at least one measurement value."})

    return prepared


@transaction.atomic
def create_measurement_profile(
    *,
    organization,
    customer: Customer,
    template_version: MeasurementTemplateVersion,
    unit_system: str,
    values_payload: list[dict],
    label: str = "Primary Measurements",
    source: str = MeasurementProfile.Source.MANUAL,
    status: str = MeasurementProfile.Status.DRAFT,
    notes: str = "",
    measured_at=None,
    created_by=None,
) -> MeasurementProfile:
    """Create a new measurement profile and validate tenant/template ownership."""
    if customer.organization_id != organization.id:
        raise exceptions.PermissionDenied("Customer does not belong to the active organization.")
    if (
        template_version.template.organization_id is not None
        and template_version.template.organization_id != organization.id
    ):
        raise exceptions.PermissionDenied("Template does not belong to the active organization.")
    if status == MeasurementProfile.Status.SUPERSEDED:
        raise exceptions.ValidationError({"status": "Cannot create a profile directly as superseded."})

    require_mandatory = status in {
        MeasurementProfile.Status.SUBMITTED,
        MeasurementProfile.Status.VERIFIED,
    }
    prepared_values = validate_and_prepare_values(
        template_version=template_version,
        unit_system=unit_system,
        values_payload=values_payload,
        require_mandatory_fields=require_mandatory,
    )

    max_ver = (
        MeasurementProfile.objects.filter(
            organization=organization,
            customer=customer,
            template_version__template=template_version.template,
        ).aggregate(m=Max("version_number"))["m"]
        or 0
    )

    # Mark previous latest profiles for same customer + template as not latest
    MeasurementProfile.objects.filter(
        organization=organization,
        customer=customer,
        template_version__template=template_version.template,
        is_latest=True,
    ).update(is_latest=False)

    now = timezone.now()
    profile = MeasurementProfile.objects.create(
        organization=organization,
        customer=customer,
        template_version=template_version,
        label=label.strip() or "Primary Measurements",
        unit_system=unit_system,
        source=source,
        status=status,
        version_number=max_ver + 1,
        is_latest=True,
        measured_at=measured_at or now,
        notes=notes.strip(),
        created_by=created_by,
        verified_by=created_by if status == MeasurementProfile.Status.VERIFIED else None,
        verified_at=now if status == MeasurementProfile.Status.VERIFIED else None,
    )

    MeasurementValue.objects.bulk_create(
        [
            MeasurementValue(
                organization=organization,
                profile=profile,
                field=entry["field"],
                numeric_value=entry["numeric_value"],
                text_value=entry["text_value"],
                unit=entry["unit"],
            )
            for entry in prepared_values
        ]
    )
    return profile


@transaction.atomic
def revise_measurement_profile(
    *,
    profile: MeasurementProfile,
    actor,
    unit_system: str | None = None,
    values_payload: list[dict] | None = None,
    label: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> MeasurementProfile:
    """
    Create a new immutable MeasurementProfile revision instead of silently overwriting
    existing measurement values (protecting confirmed order history).
    """
    if profile.status == MeasurementProfile.Status.SUPERSEDED:
        raise exceptions.ValidationError(
            "This measurement version has already been superseded. Edit the latest version instead."
        )

    new_unit = unit_system or profile.unit_system
    new_label = (label if label is not None else profile.label).strip() or profile.label
    new_notes = notes.strip() if notes is not None else profile.notes
    target_status = status or (
        MeasurementProfile.Status.VERIFIED
        if profile.status == MeasurementProfile.Status.VERIFIED
        else MeasurementProfile.Status.DRAFT
    )
    if target_status == MeasurementProfile.Status.SUPERSEDED:
        raise exceptions.ValidationError({"status": "New revision cannot start as superseded."})

    if values_payload is not None:
        raw_values = values_payload
    else:
        raw_values = [
            {
                "field_key": v.field.key,
                "numeric_value": v.numeric_value,
                "text_value": v.text_value,
            }
            for v in profile.values.select_related("field").all()
        ]

    require_mandatory = target_status in {
        MeasurementProfile.Status.SUBMITTED,
        MeasurementProfile.Status.VERIFIED,
    }
    prepared_values = validate_and_prepare_values(
        template_version=profile.template_version,
        unit_system=new_unit,
        values_payload=raw_values,
        require_mandatory_fields=require_mandatory,
    )

    max_ver = (
        MeasurementProfile.objects.filter(
            organization=profile.organization,
            customer=profile.customer,
            template_version__template=profile.template_version.template,
        ).aggregate(m=Max("version_number"))["m"]
        or profile.version_number
    )

    # Mark older version superseded and non-latest
    profile.status = MeasurementProfile.Status.SUPERSEDED
    profile.is_latest = False
    profile.save(update_fields=["status", "is_latest", "updated_at"])

    MeasurementProfile.objects.filter(
        organization=profile.organization,
        customer=profile.customer,
        template_version__template=profile.template_version.template,
        is_latest=True,
    ).update(is_latest=False)

    now = timezone.now()
    new_profile = MeasurementProfile.objects.create(
        organization=profile.organization,
        customer=profile.customer,
        template_version=profile.template_version,
        label=new_label,
        unit_system=new_unit,
        source=MeasurementProfile.Source.MANUAL,
        status=target_status,
        version_number=max_ver + 1,
        parent_profile=profile,
        is_latest=True,
        measured_at=now,
        notes=new_notes,
        created_by=actor,
        verified_by=actor if target_status == MeasurementProfile.Status.VERIFIED else None,
        verified_at=now if target_status == MeasurementProfile.Status.VERIFIED else None,
    )

    MeasurementValue.objects.bulk_create(
        [
            MeasurementValue(
                organization=profile.organization,
                profile=new_profile,
                field=entry["field"],
                numeric_value=entry["numeric_value"],
                text_value=entry["text_value"],
                unit=entry["unit"],
            )
            for entry in prepared_values
        ]
    )
    return new_profile


@transaction.atomic
def verify_measurement_profile(*, profile: MeasurementProfile, verifier) -> MeasurementProfile:
    """Confirm and verify a measurement profile after checking required fields."""
    if profile.status == MeasurementProfile.Status.SUPERSEDED:
        raise exceptions.ValidationError("Cannot verify a superseded measurement profile.")

    provided_keys = set(profile.values.values_list("field__key", flat=True))
    missing = [
        f.label
        for f in profile.template_version.fields.all()
        if f.is_required and f.key not in provided_keys
    ]
    if missing:
        raise exceptions.ValidationError(
            {"values": f"Cannot verify until required measurements are provided: {', '.join(missing)}."}
        )

    profile.status = MeasurementProfile.Status.VERIFIED
    profile.verified_by = verifier
    profile.verified_at = timezone.now()
    profile.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    return profile


@transaction.atomic
def create_measurement_request(
    *,
    organization,
    customer: Customer,
    template_version: MeasurementTemplateVersion,
    expires_in_hours: int = 72,
    notes: str = "",
    created_by=None,
) -> tuple[MeasurementRequest, str]:
    """Generate a secure expiring measurement request link and store only the token hash."""
    if customer.organization_id != organization.id:
        raise exceptions.PermissionDenied("Customer does not belong to the active organization.")
    if (
        template_version.template.organization_id is not None
        and template_version.template.organization_id != organization.id
    ):
        raise exceptions.PermissionDenied("Template does not belong to the active organization.")

    from billing.services import enforce_plan_limit

    enforce_plan_limit(organization, "monthly_measurement_requests")

    raw_token = secrets.token_urlsafe(32)
    req = MeasurementRequest.objects.create(
        organization=organization,
        customer=customer,
        template_version=template_version,
        token_hash=hash_request_token(raw_token),
        status=MeasurementRequest.Status.PENDING,
        expires_at=timezone.now() + timedelta(hours=expires_in_hours),
        notes=notes.strip(),
        created_by=created_by,
    )
    return req, raw_token


@transaction.atomic
def submit_public_measurement_request(
    *,
    measurement_request: MeasurementRequest,
    unit_system: str,
    values_payload: list[dict],
    notes: str = "",
    consent_granted: bool = False,
) -> MeasurementProfile:
    """
    Process an unauthenticated customer measurement submission.
    Always creates a 'submitted' (never 'verified') profile and records consent.
    """
    if not consent_granted:
        raise exceptions.ValidationError(
            {"consent_granted": "Explicit consent is required to submit your measurements."}
        )
    if measurement_request.status != MeasurementRequest.Status.PENDING:
        raise exceptions.ValidationError("This measurement request is no longer active.")
    if measurement_request.expires_at <= timezone.now():
        measurement_request.status = MeasurementRequest.Status.EXPIRED
        measurement_request.save(update_fields=["status", "updated_at"])
        raise exceptions.ValidationError("This measurement request has expired.")

    profile = create_measurement_profile(
        organization=measurement_request.organization,
        customer=measurement_request.customer,
        template_version=measurement_request.template_version,
        unit_system=unit_system,
        values_payload=values_payload,
        label=f"Customer Submission ({measurement_request.template_version.template.name})",
        source=MeasurementProfile.Source.CUSTOMER_SUBMITTED,
        status=MeasurementProfile.Status.SUBMITTED,
        notes=notes,
        created_by=None,
    )

    ConsentRecord.objects.create(
        organization=measurement_request.organization,
        customer=measurement_request.customer,
        consent_type=ConsentRecord.ConsentType.MEASUREMENT_SUBMISSION,
        granted=True,
        granted_at=timezone.now(),
        notes="Granted via public measurement request link.",
    )

    measurement_request.status = MeasurementRequest.Status.SUBMITTED
    measurement_request.submitted_profile = profile
    measurement_request.save(update_fields=["status", "submitted_profile", "updated_at"])

    # Link any guided reference photos uploaded during this request to the submitted profile
    measurement_request.media_assets.filter(profile__isnull=True).update(profile=profile)

    from notifications.models import Notification
    from notifications.services import create_notification

    create_notification(
        organization=measurement_request.organization,
        event_type=Notification.EventType.MEASUREMENT_SUBMITTED,
        title=f"Measurements submitted by {measurement_request.customer.full_name}",
        message=f"Review and verify v{profile.version_number} ({profile.unit_system}) before cutting.",
        link_path=f"/customers/{measurement_request.customer_id}",
    )
    return profile


@transaction.atomic
def create_measurement_share(
    *,
    organization,
    profile: MeasurementProfile,
    created_by,
    recipient_label: str = "",
    expires_in_days: int = 14,
    consent_confirmed: bool = False,
) -> tuple[MeasurementShareLink, str]:
    """Generate a consented, expiring Fit Passport share link for a verified measurement profile."""
    if profile.organization_id != organization.id:
        raise exceptions.PermissionDenied("Measurement profile does not belong to the active organization.")
    if profile.status != MeasurementProfile.Status.VERIFIED:
        raise exceptions.ValidationError(
            {"profile": "Only verified measurement profiles can be shared as a portable Fit Passport."}
        )
    if not consent_confirmed:
        raise exceptions.ValidationError(
            {"consent_confirmed": "Customer consent must be confirmed before generating a share link."}
        )

    raw_token = secrets.token_urlsafe(32)
    share = MeasurementShareLink.objects.create(
        organization=organization,
        customer=profile.customer,
        profile=profile,
        token_hash=hash_request_token(raw_token),
        recipient_label=recipient_label.strip(),
        status=MeasurementShareLink.Status.ACTIVE,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
        created_by=created_by,
    )
    ConsentRecord.objects.create(
        organization=organization,
        customer=profile.customer,
        consent_type=ConsentRecord.ConsentType.MEASUREMENT_SHARING,
        granted=True,
        granted_at=timezone.now(),
        notes=f"Portable Fit Passport shared ({recipient_label.strip() or 'General share'}).",
    )
    return share, raw_token


def get_active_share_or_error(raw_token: str) -> MeasurementShareLink:
    cleaned = raw_token.strip()
    # Accept either raw token or pasted /fit/<token> URL
    if "/fit/" in cleaned:
        cleaned = cleaned.split("/fit/")[-1].strip().strip("/")
    token_hash = hash_request_token(cleaned)
    share = (
        MeasurementShareLink.objects.select_related(
            "organization",
            "customer",
            "profile__template_version__template",
        )
        .prefetch_related("profile__values__field")
        .filter(token_hash=token_hash)
        .first()
    )
    if not share:
        raise exceptions.NotFound("Fit Passport link not found.")
    if share.status == MeasurementShareLink.Status.REVOKED:
        raise exceptions.ValidationError("This Fit Passport link has been revoked.")
    if share.status == MeasurementShareLink.Status.EXPIRED or share.expires_at <= timezone.now():
        if share.status == MeasurementShareLink.Status.ACTIVE:
            share.status = MeasurementShareLink.Status.EXPIRED
            share.save(update_fields=["status", "updated_at"])
        raise exceptions.ValidationError("This Fit Passport link has expired.")
    return share


@transaction.atomic
def import_measurement_from_share(
    *,
    organization,
    customer: Customer,
    raw_token: str,
    imported_by,
) -> MeasurementProfile:
    """
    Import a verified shared Fit Passport into another workspace's customer record.
    Always marks imported profile as source='imported' and status='needs_review'
    so the receiving artisan confirms fit before cutting.
    """
    if customer.organization_id != organization.id:
        raise exceptions.PermissionDenied("Customer does not belong to the active organization.")

    share = get_active_share_or_error(raw_token)
    source_profile = share.profile
    source_template_version = source_profile.template_version

    # If the shared profile uses a custom template from another org, map matching keys to a system template if available
    target_template_version = source_template_version
    if (
        source_template_version.template.organization_id is not None
        and source_template_version.template.organization_id != organization.id
    ):
        system_fallback = (
            MeasurementTemplateVersion.objects.select_related("template")
            .prefetch_related("fields")
            .filter(
                template__organization__isnull=True,
                template__category=source_template_version.template.category,
                is_published=True,
            )
            .order_by("-version_number")
            .first()
        )
        if not system_fallback:
            raise exceptions.ValidationError(
                "This Fit Passport uses a private custom template that cannot be mapped automatically."
            )
        target_template_version = system_fallback

    allowed_keys = {f.key for f in target_template_version.fields.all()}
    values_payload = [
        {
            "field_key": v.field.key,
            "numeric_value": v.numeric_value,
            "text_value": v.text_value,
        }
        for v in source_profile.values.select_related("field").all()
        if v.field.key in allowed_keys
    ]

    imported = create_measurement_profile(
        organization=organization,
        customer=customer,
        template_version=target_template_version,
        unit_system=source_profile.unit_system,
        values_payload=values_payload,
        label=f"Imported from {share.organization.name} ({source_profile.label})"[:120],
        source=MeasurementProfile.Source.IMPORTED,
        status=MeasurementProfile.Status.NEEDS_REVIEW,
        notes=f"Imported via consented Fit Passport from {share.organization.name}. Review & verify before cutting.",
        created_by=imported_by,
    )

    share.access_count += 1
    share.last_accessed_at = timezone.now()
    share.save(update_fields=["access_count", "last_accessed_at", "updated_at"])
    return imported
