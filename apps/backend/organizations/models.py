from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Organization(TimeStampedModel):
    """Multi-tenant artisan business workspace."""

    class Category(models.TextChoices):
        TAILOR = "tailor", "Tailor"
        SHOEMAKER = "shoemaker", "Shoemaker"
        LEATHERWORKER = "leatherworker", "Leatherworker"
        OTHER = "other", "Other"

    class UnitSystem(models.TextChoices):
        CM = "cm", "Centimetres (cm)"
        IN = "in", "Inches (in)"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, db_index=True)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.TAILOR)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    currency = models.CharField(max_length=3, default="NGN")
    preferred_unit = models.CharField(max_length=8, choices=UnitSystem.choices, default=UnitSystem.CM)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"


class Membership(TimeStampedModel):
    """Associates a user with an organization and role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        ARTISAN = "artisan", "Artisan"
        SALES_ASSISTANT = "sales_assistant", "Sales Assistant"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        SUSPENDED = "suspended", "Suspended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.ARTISAN)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        unique_together = [("user", "organization")]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} -> {self.organization.name} ({self.role})"


class OrganizationInvitation(TimeStampedModel):
    """Expiring secure invitation for a team member to join an organization."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=32, choices=Membership.Role.choices, default=Membership.Role.ARTISAN)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    expires_at = models.DateTimeField()
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "email", "status"]),
        ]

    def __str__(self) -> str:
        return f"Invite {self.email} -> {self.organization.name} ({self.role}, {self.status})"
