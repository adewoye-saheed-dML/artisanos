from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class EscrowTransaction(TimeStampedModel):
    """
    Escrow protection ledger ensuring customers only release full payment
    after inspecting and confirming completed artisan work or delivered goods.
    """

    class Status(models.TextChoices):
        AWAITING_FUNDING = "awaiting_funding", "Awaiting Escrow Funding"
        FUNDED_HELD = "funded_held", "Funded & Held in Escrow"
        WORK_SUBMITTED = "work_submitted", "Work Completed — Awaiting Customer Confirmation"
        RELEASED = "released", "Completed & Released to Artisan"
        DISPUTED = "disputed", "Disputed — Funds Frozen"
        REFUNDED = "refunded", "Refunded to Customer"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=40, unique=True, db_index=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="escrow_transactions",
    )
    customer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_escrows",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrows",
    )
    inquiry = models.ForeignKey(
        "catalog.StorefrontInquiry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrows",
    )
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=32)
    customer_email = models.EmailField(blank=True, default="")
    job_title = models.CharField(max_length=180)
    job_description = models.TextField(blank=True, default="")

    # Financials (strict Decimal — never float)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    materials_advance_pct = models.PositiveSmallIntegerField(default=0)
    materials_advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    held_in_escrow_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    artisan_payout_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")

    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.AWAITING_FUNDING,
        db_index=True,
    )
    payment_provider = models.CharField(max_length=24, default="paystack")
    provider_payload = models.JSONField(default=dict, blank=True)

    # SHA-256 hash of 6-digit release PIN issued exclusively to the customer on funding
    completion_pin_hash = models.CharField(max_length=64, blank=True, default="")
    artisan_completion_notes = models.TextField(blank=True, default="")
    dispute_reason = models.TextField(blank=True, default="")
    resolution_notes = models.TextField(blank=True, default="")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_escrows",
    )

    funded_at = models.DateTimeField(null=True, blank=True)
    work_submitted_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["customer_user", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.organization.name} · {self.currency} {self.total_amount} · {self.status})"


class EscrowEvent(TimeStampedModel):
    """Immutable audit timeline of every escrow state transition."""

    escrow = models.ForeignKey(
        EscrowTransaction,
        on_delete=models.CASCADE,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escrow_events",
    )
    event_type = models.CharField(max_length=40, db_index=True)
    from_status = models.CharField(max_length=24, blank=True, default="")
    to_status = models.CharField(max_length=24)
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.escrow.reference}: {self.event_type} -> {self.to_status}"
