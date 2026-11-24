from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel, TimeStampedModel


class Plan(TimeStampedModel):
    """SaaS subscription plan with enforceable workspace entitlements and escrow fee tier."""

    code = models.SlugField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True, default="")
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    annual_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="NGN")
    max_members = models.PositiveIntegerField(default=2)
    max_customers = models.PositiveIntegerField(default=50)
    max_monthly_measurement_requests = models.PositiveIntegerField(default=25)
    max_products = models.PositiveIntegerField(default=15)
    max_service_wards = models.PositiveIntegerField(default=1)
    escrow_fee_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.00"))
    monthly_free_boosts = models.PositiveIntegerField(default=0)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "monthly_price"]

    def __str__(self) -> str:
        return f"{self.name} ({self.currency} {self.monthly_price}/mo)"


class Subscription(TimeStampedModel):
    """Active SaaS subscription binding an organization to a Plan."""

    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELLED = "cancelled", "Cancelled"

    class Provider(models.TextChoices):
        MANUAL = "manual", "Manual / Free"
        PAYSTACK = "paystack", "Paystack"

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    billing_cycle = models.CharField(
        max_length=16,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    provider = models.CharField(max_length=24, choices=Provider.choices, default=Provider.MANUAL)
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.organization.name} -> {self.plan.name} ({self.status})"


class PaymentTransaction(TenantOwnedModel):
    """Auditable billing payment record verified exclusively via Paystack webhooks/verify API or admin."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class Purpose(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription Plan"
        BOOST = "boost", "Marketplace Spotlight Boost"

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    purpose = models.CharField(
        max_length=24,
        choices=Purpose.choices,
        default=Purpose.SUBSCRIPTION,
        db_index=True,
    )
    billing_cycle = models.CharField(
        max_length=16,
        choices=Subscription.BillingCycle.choices,
        default=Subscription.BillingCycle.MONTHLY,
    )
    reference = models.CharField(max_length=120, unique=True, db_index=True)
    provider = models.CharField(max_length=24, default="paystack")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NGN")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    authorization_url = models.URLField(max_length=500, blank=True, default="")
    access_code = models.CharField(max_length=120, blank=True, default="")
    provider_payload = models.JSONField(default=dict, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_payment_transactions",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["purpose", "status", "verified_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.purpose} · {self.amount} {self.currency}, {self.status})"


class MarketplaceBoost(TenantOwnedModel):
    """Paid or plan-included spotlight boost pinning an artisan storefront or product to top local results."""

    class BoostType(models.TextChoices):
        AREA_7D = "area_7d", "7-Day Neighborhood Spotlight"
        LGA_30D = "lga_30d", "30-Day LGA Top Spotlight"
        PRODUCT_7D = "product_7d", "7-Day Product / Service Boost"

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    boost_type = models.CharField(max_length=24, choices=BoostType.choices, db_index=True)
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="marketplace_boosts",
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="NGN")
    duration_days = models.PositiveSmallIntegerField(default=7)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    used_plan_credit = models.BooleanField(default=False)
    payment_transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="boosts",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_boosts",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "ends_at"], name="bill_boost_active_idx"),
            models.Index(fields=["organization", "status", "ends_at"], name="bill_boost_org_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.organization.name} · {self.get_boost_type_display()} ({self.status})"


class AuditLog(TimeStampedModel):
    """Immutable audit log for platform admin and subscription/billing events."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.target_type}:{self.target_id})"
