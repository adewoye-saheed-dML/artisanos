from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from customers.models import ConsentRecord, Customer
from organizations.models import Membership

from .models import MeasurementProfile, MeasurementRequest, MediaAccessLog, MediaAsset

ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_CAPTURE_BYTES = 8 * 1024 * 1024  # 8 MB
DEFAULT_RETENTION_DAYS = 30

# Roles permitted to view or upload sensitive customer body reference photos
PHOTO_ACCESS_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.ARTISAN,
}


def get_client_ip(request) -> str | None:
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _detect_image_magic(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


@transaction.atomic
def store_guided_capture(
    *,
    organization,
    customer: Customer,
    uploaded_file,
    view_angle: str,
    photo_consent_granted: bool,
    allow_model_training: bool = False,
    quality_metadata: dict | None = None,
    profile: MeasurementProfile | None = None,
    measurement_request: MeasurementRequest | None = None,
    uploaded_by=None,
    ip_address: str | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> MediaAsset:
    """Validate image magic bytes, record explicit photo consent, and store protected MediaAsset."""
    if customer.organization_id != organization.id:
        raise exceptions.PermissionDenied("Customer does not belong to the active organization.")
    if not photo_consent_granted:
        raise exceptions.ValidationError(
            {"photo_consent_granted": "Explicit photo capture consent is required before storing reference images."}
        )
    if profile is not None:
        if profile.organization_id != organization.id or profile.customer_id != customer.id:
            raise exceptions.ValidationError({"profile": "Measurement profile does not match this customer."})

    if uploaded_file is None:
        raise exceptions.ValidationError({"file": "An image file is required."})
    if uploaded_file.size > MAX_CAPTURE_BYTES:
        raise exceptions.ValidationError({"file": "Image exceeds maximum allowed size of 8 MB."})
    if uploaded_file.size == 0:
        raise exceptions.ValidationError({"file": "Uploaded image file is empty."})

    head = uploaded_file.read(16)
    uploaded_file.seek(0)
    detected_mime = _detect_image_magic(head)
    if detected_mime not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise exceptions.ValidationError(
            {"file": "Only valid JPEG, PNG, or WebP images are permitted."}
        )

    now = timezone.now()
    consent = ConsentRecord.objects.create(
        organization=organization,
        customer=customer,
        consent_type=ConsentRecord.ConsentType.PHOTO_CAPTURE,
        granted=True,
        granted_at=now,
        notes=(
            f"Explicit consent for {view_angle} guided reference photo "
            f"(retention: {retention_days} days; model training opt-in: {bool(allow_model_training)})."
        ),
    )

    asset = MediaAsset.objects.create(
        organization=organization,
        customer=customer,
        profile=profile,
        measurement_request=measurement_request,
        view_angle=view_angle,
        file=uploaded_file,
        content_type=detected_mime,
        file_size_bytes=uploaded_file.size,
        quality_metadata=quality_metadata or {},
        consent_record=consent,
        allow_model_training=bool(allow_model_training),
        retention_expires_at=now + timedelta(days=retention_days),
        status=MediaAsset.Status.ACTIVE,
        uploaded_by=uploaded_by,
    )

    MediaAccessLog.objects.create(
        organization=organization,
        asset=asset,
        accessed_by=uploaded_by,
        action=MediaAccessLog.Action.UPLOADED,
        ip_address=ip_address,
        notes=f"Uploaded {view_angle} capture ({uploaded_file.size} bytes).",
    )
    return asset


@transaction.atomic
def permanently_delete_media_asset(
    *,
    asset: MediaAsset,
    actor=None,
    ip_address: str | None = None,
    action: str = MediaAccessLog.Action.DELETED,
    reason: str = "Deleted by authorized workspace member.",
) -> MediaAsset:
    """Physically delete raw image bytes from storage and mark metadata deleted/expired."""
    if asset.file:
        asset.file.delete(save=False)
    asset.file = ""
    asset.file_size_bytes = 0
    asset.status = (
        MediaAsset.Status.EXPIRED
        if action == MediaAccessLog.Action.PURGED
        else MediaAsset.Status.DELETED
    )
    asset.deleted_at = timezone.now()
    asset.save(update_fields=["file", "file_size_bytes", "status", "deleted_at", "updated_at"])

    MediaAccessLog.objects.create(
        organization=asset.organization,
        asset=asset,
        accessed_by=actor,
        action=action,
        ip_address=ip_address,
        notes=reason[:255],
    )
    return asset


def purge_expired_media_assets() -> int:
    """Physically delete all active media assets whose retention window has expired."""
    expired = MediaAsset.objects.filter(
        status=MediaAsset.Status.ACTIVE,
        retention_expires_at__lte=timezone.now(),
    )
    count = 0
    for asset in expired:
        permanently_delete_media_asset(
            asset=asset,
            actor=None,
            action=MediaAccessLog.Action.PURGED,
            reason="Automatic retention expiry purge.",
        )
        count += 1
    return count
