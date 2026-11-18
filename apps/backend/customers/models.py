from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class Customer(TenantOwnedModel):
    """Organization-scoped customer profile."""

    class ContactMethod(models.TextChoices):
        PHONE = "phone", "Phone"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"

    full_name = models.CharField(max_length=150, db_index=True)
    phone = models.CharField(max_length=32, db_index=True)
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=ContactMethod.choices,
        default=ContactMethod.PHONE,
    )
    notes = models.TextField(blank=True, default="")
    is_archived = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customers",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_archived", "full_name"]),
            models.Index(fields=["organization", "phone"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.organization.name})"


class ConsentRecord(TenantOwnedModel):
    """Explicit customer consent audit record for measurement submissions or future media capture."""

    class ConsentType(models.TextChoices):
        MEASUREMENT_SUBMISSION = "measurement_submission", "Measurement Submission"
        MEASUREMENT_SHARING = "measurement_sharing", "Measurement Portability & Sharing"
        PHOTO_CAPTURE = "photo_capture", "Photo Capture"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="consent_records",
    )
    consent_type = models.CharField(max_length=40, choices=ConsentType.choices)
    granted = models.BooleanField(default=False)
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
