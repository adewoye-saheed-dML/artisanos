from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Organization(TimeStampedModel):
    """Multi-tenant artisan business workspace across all trades, goods & services."""

    class Category(models.TextChoices):
        TAILOR = "tailor", "Tailor & Fashion Designer"
        SHOEMAKER = "shoemaker", "Shoemaker & Cobbler"
        LEATHERWORKER = "leatherworker", "Leatherworker & Bag Maker"
        ELECTRICIAN = "electrician", "Electrician & Solar Tech"
        PLUMBER = "plumber", "Plumber & Pipefitter"
        CARPENTER = "carpenter", "Carpenter & Furniture Maker"
        MECHANIC = "mechanic", "Auto Mechanic & Technician"
        WELDER = "welder", "Welder & Metal Fabricator"
        PAINTER = "painter", "Painter & Interior Decorator"
        AC_TECHNICIAN = "ac_technician", "AC & Refrigeration Tech"
        MASON = "mason", "Mason, Tiler & Bricklayer"
        HAIR_BEAUTY = "hair_beauty", "Hair Stylist, Barber & Beauty"
        CATERER = "caterer", "Caterer & Baker"
        PHONE_REPAIR = "phone_repair", "Phone & Electronics Repair"
        GENERATOR_TECH = "generator_tech", "Generator & Inverter Tech"
        CLEANER = "cleaner", "Cleaning & Laundry Services"
        OTHER = "other", "Other Artisan / Craft"

    class UnitSystem(models.TextChoices):
        CM = "cm", "Centimetres (cm)"
        IN = "in", "Inches (in)"

    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "available", "Available for Work"
        BUSY = "busy", "Busy / Limited Slots"
        OFFLINE = "offline", "Offline / Not Taking Calls"

    class VerificationStatus(models.TextChoices):
        UNSUBMITTED = "unsubmitted", "KYC Not Submitted"
        PENDING_REVIEW = "pending_review", "Pending KYC Review"
        APPROVED = "approved", "Verified & Approved"
        REJECTED = "rejected", "Verification Rejected"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, db_index=True)
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.TAILOR,
        db_index=True,
    )
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="Nigeria")
    # Hyper-local Nigerian administrative hierarchy: State -> LGA -> Ward -> Polling Unit
    state = models.ForeignKey(
        "locations.NigerianState",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations",
    )
    lga = models.ForeignKey(
        "locations.NigerianLGA",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations",
    )
    ward = models.ForeignKey(
        "locations.NigerianWard",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations",
    )
    polling_unit = models.ForeignKey(
        "locations.PollingUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organizations",
    )
    service_wards = models.ManyToManyField(
        "locations.NigerianWard",
        blank=True,
        related_name="covering_organizations",
    )
    landmark = models.CharField(max_length=200, blank=True, default="")
    # Call-out & patronage capabilities
    availability_status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        db_index=True,
    )
    available_for_callout = models.BooleanField(default=True, db_index=True)
    offers_goods = models.BooleanField(default=True)
    offers_services = models.BooleanField(default=True)
    callout_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    skills = models.JSONField(default=list, blank=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    verification_status = models.CharField(
        max_length=24,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNSUBMITTED,
        db_index=True,
    )
    currency = models.CharField(max_length=3, default="NGN")
    preferred_unit = models.CharField(max_length=8, choices=UnitSystem.choices, default=UnitSystem.CM)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "category", "state"]),
            models.Index(fields=["is_active", "ward"]),
            models.Index(fields=["is_active", "polling_unit"]),
        ]

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


class ArtisanVerification(TimeStampedModel):
    """Strict anti-scam KYC dossier (NIN, CAC, guarantor & payout bank) for an artisan organization."""

    class GovernmentIdType(models.TextChoices):
        NIN_SLIP = "nin_slip", "NIN Slip / National ID"
        VOTERS_CARD = "voters_card", "Permanent Voter's Card (PVC)"
        DRIVERS_LICENSE = "drivers_license", "Nigerian Driver's License"
        INTL_PASSPORT = "intl_passport", "Nigerian International Passport"

    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name="kyc_verification",
    )
    nin_hash = models.CharField(max_length=64, db_index=True)
    nin_last4 = models.CharField(max_length=4)
    government_id_type = models.CharField(
        max_length=24,
        choices=GovernmentIdType.choices,
        default=GovernmentIdType.NIN_SLIP,
    )
    cac_number = models.CharField(max_length=32, blank=True, default="", db_index=True)
    cac_business_name = models.CharField(max_length=160, blank=True, default="")
    guarantor_name = models.CharField(max_length=150, blank=True, default="")
    guarantor_phone = models.CharField(max_length=32, blank=True, default="")
    bank_name = models.CharField(max_length=80, blank=True, default="")
    bank_account_number = models.CharField(max_length=20, blank=True, default="")
    bank_account_name = models.CharField(max_length=150, blank=True, default="")
    status = models.CharField(
        max_length=24,
        choices=Organization.VerificationStatus.choices,
        default=Organization.VerificationStatus.PENDING_REVIEW,
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_kyc_verifications",
    )
    submitted_at = models.DateTimeField()
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_kyc_verifications",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    review_notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"KYC {self.organization.name} ({self.status}, NIN ***{self.nin_last4})"


class VerificationDocument(TimeStampedModel):
    """Uploaded KYC supporting document (NIN slip, CAC certificate, utility bill, trade cert)."""

    class DocumentType(models.TextChoices):
        NIN_SLIP = "nin_slip", "NIN Slip / Government ID"
        CAC_CERTIFICATE = "cac_certificate", "CAC Certificate"
        UTILITY_BILL = "utility_bill", "Utility Bill / Workshop Address Proof"
        TRADE_CERTIFICATE = "trade_certificate", "Trade Test / Guild Certificate"
        WORKSHOP_PHOTO = "workshop_photo", "Workshop & Artisan Photo"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="verification_documents",
    )
    verification = models.ForeignKey(
        ArtisanVerification,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=32, choices=DocumentType.choices, db_index=True)
    file = models.FileField(upload_to="kyc_documents/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    file_size_bytes = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_kyc_documents",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "document_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.document_type}"
