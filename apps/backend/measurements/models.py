from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TenantOwnedModel


class MeasurementProfile(TenantOwnedModel):
    """Versioned customer measurement record tied to a template version."""

    class UnitSystem(models.TextChoices):
        CM = "cm", "Centimetres (cm)"
        IN = "in", "Inches (in)"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        CUSTOMER_SUBMITTED = "customer_submitted", "Customer Submitted"
        CAMERA_ASSISTED = "camera_assisted", "Camera Assisted"
        IMPORTED = "imported", "Imported"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        NEEDS_REVIEW = "needs_review", "Needs Review"
        VERIFIED = "verified", "Verified"
        SUPERSEDED = "superseded", "Superseded"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="measurement_profiles",
    )
    template_version = models.ForeignKey(
        "measurement_templates.MeasurementTemplateVersion",
        on_delete=models.PROTECT,
        related_name="measurement_profiles",
    )
    label = models.CharField(max_length=120, default="Primary Measurements")
    unit_system = models.CharField(max_length=8, choices=UnitSystem.choices, default=UnitSystem.CM)
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    version_number = models.PositiveIntegerField(default=1)
    parent_profile = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    is_latest = models.BooleanField(default=True, db_index=True)
    measured_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_measurement_profiles",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_measurement_profiles",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-measured_at", "-version_number", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "customer", "is_latest"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.customer.full_name} - {self.label} v{self.version_number} ({self.status})"


class MeasurementValue(TenantOwnedModel):
    """Single field value inside a MeasurementProfile."""

    profile = models.ForeignKey(
        MeasurementProfile,
        on_delete=models.CASCADE,
        related_name="values",
    )
    field = models.ForeignKey(
        "measurement_templates.MeasurementField",
        on_delete=models.PROTECT,
        related_name="recorded_values",
    )
    numeric_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    text_value = models.CharField(max_length=120, blank=True, default="")
    unit = models.CharField(max_length=10, default="cm")

    class Meta:
        unique_together = [("profile", "field")]
        ordering = ["field__display_order", "field__label"]

    def __str__(self) -> str:
        val = self.text_value if self.text_value else self.numeric_value
        return f"{self.field.key}: {val} {self.unit}"


class MeasurementRequest(TenantOwnedModel):
    """Expiring secure link allowing a customer to submit measurements without an account."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUBMITTED = "submitted", "Submitted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="measurement_requests",
    )
    template_version = models.ForeignKey(
        "measurement_templates.MeasurementTemplateVersion",
        on_delete=models.PROTECT,
        related_name="measurement_requests",
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField()
    submitted_profile = models.ForeignKey(
        MeasurementProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originating_requests",
    )
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_measurement_requests",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
        ]


class MeasurementShareLink(TenantOwnedModel):
    """Consented, expiring read-only Fit Passport link for measurement portability."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="measurement_share_links",
    )
    profile = models.ForeignKey(
        MeasurementProfile,
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    recipient_label = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    expires_at = models.DateTimeField()
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_measurement_shares",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "customer", "status"]),
        ]


class MediaAsset(TenantOwnedModel):
    """
    Protected reference photo captured during guided front/side sessions.
    Stored outside public static paths, bound to explicit consent and retention expiry,
    and physically deleted from disk on deletion/purge.
    """

    class ViewAngle(models.TextChoices):
        FRONT = "front", "Front View"
        SIDE = "side", "Side View"
        BACK = "back", "Back View"
        DETAIL = "detail", "Fit Detail"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DELETED = "deleted", "Deleted"
        EXPIRED = "expired", "Expired"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="media_assets",
    )
    profile = models.ForeignKey(
        MeasurementProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_assets",
    )
    measurement_request = models.ForeignKey(
        MeasurementRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_assets",
    )
    view_angle = models.CharField(
        max_length=20,
        choices=ViewAngle.choices,
        default=ViewAngle.FRONT,
    )
    file = models.FileField(upload_to="protected_captures/%Y/%m/%d/", blank=True, default="")
    content_type = models.CharField(max_length=64, default="image/jpeg")
    file_size_bytes = models.PositiveIntegerField(default=0)
    quality_metadata = models.JSONField(default=dict, blank=True)
    consent_record = models.ForeignKey(
        "customers.ConsentRecord",
        on_delete=models.PROTECT,
        related_name="media_assets",
    )
    allow_model_training = models.BooleanField(default=False)
    retention_expires_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_media_assets",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "customer", "status"]),
            models.Index(fields=["status", "retention_expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.customer.full_name} ({self.view_angle}, {self.status})"


class MediaAccessLog(TenantOwnedModel):
    """Immutable audit trail for uploads, views, deletions, and retention purges."""

    class Action(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        VIEWED = "viewed", "Viewed"
        DELETED = "deleted", "Deleted"
        PURGED = "purged", "Retention Purged"

    asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name="access_logs",
    )
    accessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_access_logs",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["asset", "created_at"]),
        ]
