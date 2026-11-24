import hashlib
import re

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from billing.models import AuditLog
from catalog.services import get_or_create_storefront
from notifications.models import Notification
from notifications.services import create_notification

from .models import ArtisanVerification, Organization, VerificationDocument

NIN_REGEX = re.compile(r"^\d{11}$")
CAC_REGEX = re.compile(r"^(RC|BN|IT)\d{5,9}$")
NUBAN_REGEX = re.compile(r"^\d{10}$")

ALLOWED_KYC_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_KYC_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


def hash_nin(raw_nin: str) -> str:
    return hashlib.sha256(raw_nin.encode("utf-8")).hexdigest()


def normalize_and_validate_nin(raw_nin: str) -> str:
    cleaned = re.sub(r"[\s-]+", "", (raw_nin or "").strip())
    if not NIN_REGEX.match(cleaned):
        raise exceptions.ValidationError(
            {"nin": "NIN must be an exact 11-digit Nigerian National Identification Number."}
        )
    return cleaned


def normalize_and_validate_cac(raw_cac: str) -> str:
    cleaned = re.sub(r"[\s-]+", "", (raw_cac or "").strip().upper())
    if not cleaned:
        return ""
    if not CAC_REGEX.match(cleaned):
        raise exceptions.ValidationError(
            {"cac_number": "CAC number must start with RC, BN, or IT followed by 5 to 9 digits (e.g. RC1234567 or BN2345678)."}
        )
    return cleaned


def normalize_and_validate_nuban(raw_account: str) -> str:
    cleaned = re.sub(r"[\s-]+", "", (raw_account or "").strip())
    if not cleaned:
        return ""
    if not NUBAN_REGEX.match(cleaned):
        raise exceptions.ValidationError(
            {"bank_account_number": "Bank account number must be a valid 10-digit Nigerian NUBAN."}
        )
    return cleaned


@transaction.atomic
def submit_artisan_kyc(
    *,
    organization: Organization,
    submitted_by,
    nin: str = "",
    government_id_type: str = ArtisanVerification.GovernmentIdType.NIN_SLIP,
    cac_number: str = "",
    cac_business_name: str = "",
    guarantor_name: str = "",
    guarantor_phone: str = "",
    bank_name: str = "",
    bank_account_number: str = "",
    bank_account_name: str = "",
) -> ArtisanVerification:
    """
    Create or update an artisan organization's KYC verification dossier.
    Blocks NINs already linked to suspended or banned organizations to prevent repeat scammers.
    """
    existing = ArtisanVerification.objects.filter(organization=organization).first()

    if nin.strip():
        cleaned_nin = normalize_and_validate_nin(nin)
        nin_digest = hash_nin(cleaned_nin)
        nin_last4 = cleaned_nin[-4:]
        # Block NINs tied to suspended workspaces (anti-scam safeguard)
        banned_match = (
            ArtisanVerification.objects.select_related("organization")
            .filter(nin_hash=nin_digest, organization__is_active=False)
            .exclude(organization=organization)
            .exists()
        )
        if banned_match:
            raise exceptions.ValidationError(
                {"nin": "This NIN is associated with a suspended account and cannot be registered."}
            )
    elif existing:
        nin_digest = existing.nin_hash
        nin_last4 = existing.nin_last4
    else:
        raise exceptions.ValidationError(
            {"nin": "A valid 11-digit Nigerian NIN is required for artisan verification."}
        )

    cleaned_cac = normalize_and_validate_cac(cac_number)
    cleaned_nuban = normalize_and_validate_nuban(bank_account_number)
    now = timezone.now()

    verification, _ = ArtisanVerification.objects.update_or_create(
        organization=organization,
        defaults={
            "nin_hash": nin_digest,
            "nin_last4": nin_last4,
            "government_id_type": government_id_type or ArtisanVerification.GovernmentIdType.NIN_SLIP,
            "cac_number": cleaned_cac,
            "cac_business_name": cac_business_name.strip()[:160],
            "guarantor_name": guarantor_name.strip()[:150],
            "guarantor_phone": guarantor_phone.strip()[:32],
            "bank_name": bank_name.strip()[:80],
            "bank_account_number": cleaned_nuban,
            "bank_account_name": bank_account_name.strip()[:150],
            "status": Organization.VerificationStatus.PENDING_REVIEW,
            "submitted_by": submitted_by,
            "submitted_at": now,
            "rejection_reason": "",
        },
    )

    organization.verification_status = Organization.VerificationStatus.PENDING_REVIEW
    organization.is_verified = False
    organization.save(update_fields=["verification_status", "is_verified", "updated_at"])

    # Keep storefront unpublished until platform admin verifies documents
    sf = get_or_create_storefront(organization)
    if sf.is_published:
        sf.is_published = False
        sf.save(update_fields=["is_published", "updated_at"])

    return verification


@transaction.atomic
def upload_verification_document(
    *,
    organization: Organization,
    uploaded_by,
    document_type: str,
    uploaded_file,
) -> VerificationDocument:
    verification = ArtisanVerification.objects.filter(organization=organization).first()
    if not verification:
        raise exceptions.ValidationError(
            "Submit your NIN and KYC details first before uploading supporting documents."
        )

    content_type = getattr(uploaded_file, "content_type", "") or ""
    if content_type not in ALLOWED_KYC_CONTENT_TYPES:
        raise exceptions.ValidationError(
            {"file": "Only JPG, PNG, WEBP, or PDF verification documents are allowed."}
        )
    if uploaded_file.size > MAX_KYC_FILE_BYTES:
        raise exceptions.ValidationError({"file": "Document file size must not exceed 5 MB."})

    doc = VerificationDocument.objects.create(
        organization=organization,
        verification=verification,
        document_type=document_type,
        file=uploaded_file,
        original_filename=(getattr(uploaded_file, "name", "document") or "document")[:255],
        content_type=content_type,
        file_size_bytes=uploaded_file.size,
        uploaded_by=uploaded_by,
    )
    return doc


@transaction.atomic
def approve_artisan_kyc(
    *,
    organization: Organization,
    reviewer,
    notes: str = "",
) -> ArtisanVerification:
    verification = ArtisanVerification.objects.filter(organization=organization).first()
    if not verification:
        raise exceptions.ValidationError("This organization has not submitted KYC details yet.")

    now = timezone.now()
    verification.status = Organization.VerificationStatus.APPROVED
    verification.reviewed_by = reviewer
    verification.reviewed_at = now
    verification.review_notes = notes.strip()
    verification.rejection_reason = ""
    verification.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "rejection_reason",
            "updated_at",
        ]
    )

    organization.verification_status = Organization.VerificationStatus.APPROVED
    organization.is_verified = True
    organization.save(update_fields=["verification_status", "is_verified", "updated_at"])

    # Auto-publish storefront once KYC passes anti-scam verification
    sf = get_or_create_storefront(organization)
    sf.is_published = True
    sf.save(update_fields=["is_published", "updated_at"])

    AuditLog.objects.create(
        organization=organization,
        actor=reviewer,
        action="artisan_kyc_approved",
        target_type="ArtisanVerification",
        target_id=str(verification.id),
        reason=notes.strip() or "Artisan NIN/CAC KYC approved.",
        metadata={
            "nin_last4": verification.nin_last4,
            "cac_number": verification.cac_number,
        },
    )
    create_notification(
        organization=organization,
        event_type=Notification.EventType.SYSTEM,
        title="KYC Approved — Your Storefront Is Now Live!",
        message="Your NIN/CAC identity verification has been approved. Nearby customers in your neighborhood can now discover and hire you with Escrow protection.",
        link_path="/verification",
    )
    return verification


@transaction.atomic
def reject_artisan_kyc(
    *,
    organization: Organization,
    reviewer,
    reason: str,
) -> ArtisanVerification:
    cleaned_reason = reason.strip()
    if len(cleaned_reason) < 5:
        raise exceptions.ValidationError({"reason": "Provide a clear rejection reason for the artisan."})

    verification = ArtisanVerification.objects.filter(organization=organization).first()
    if not verification:
        raise exceptions.ValidationError("This organization has not submitted KYC details yet.")

    now = timezone.now()
    verification.status = Organization.VerificationStatus.REJECTED
    verification.reviewed_by = reviewer
    verification.reviewed_at = now
    verification.rejection_reason = cleaned_reason
    verification.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"]
    )

    organization.verification_status = Organization.VerificationStatus.REJECTED
    organization.is_verified = False
    organization.save(update_fields=["verification_status", "is_verified", "updated_at"])

    sf = get_or_create_storefront(organization)
    if sf.is_published:
        sf.is_published = False
        sf.save(update_fields=["is_published", "updated_at"])

    AuditLog.objects.create(
        organization=organization,
        actor=reviewer,
        action="artisan_kyc_rejected",
        target_type="ArtisanVerification",
        target_id=str(verification.id),
        reason=cleaned_reason,
    )
    create_notification(
        organization=organization,
        event_type=Notification.EventType.SYSTEM,
        title="KYC Verification Needs Attention",
        message=f"Verification was not approved: {cleaned_reason}. Update your NIN/CAC or documents and resubmit.",
        link_path="/verification",
    )
    return verification
