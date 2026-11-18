from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class Order(TenantOwnedModel):
    """Organization-scoped tailoring or custom artisan order."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        AWAITING_MEASUREMENTS = "awaiting_measurements", "Awaiting Measurements"
        QUOTED = "quoted", "Quoted"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PRODUCTION = "in_production", "In Production"
        FITTING = "fitting", "Fitting"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        ON_HOLD = "on_hold", "On Hold"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"

    class DeliveryMethod(models.TextChoices):
        PICKUP = "pickup", "Studio Pickup"
        DELIVERY = "delivery", "Local Delivery"
        SHIPPING = "shipping", "Courier / Shipping"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    order_number = models.CharField(max_length=32, db_index=True)
    garment_type = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    measurement_profile = models.ForeignKey(
        "measurements.MeasurementProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    measurement_snapshot = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    quoted_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    agreed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="NGN")
    payment_status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    expected_completion_date = models.DateField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
    )
    customer_instructions = models.TextField(blank=True, default="")
    internal_notes = models.TextField(blank=True, default="")
    category_options = models.JSONField(default=dict, blank=True)
    delivery_method = models.CharField(
        max_length=24,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.PICKUP,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_orders",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("organization", "order_number")]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
            models.Index(fields=["organization", "customer"]),
        ]

    def __str__(self) -> str:
        return f"{self.order_number} - {self.garment_type}"


class OrderStatusEvent(TenantOwnedModel):
    """Immutable audit log of order status transitions."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_events",
    )
    from_status = models.CharField(max_length=32, blank=True, default="")
    to_status = models.CharField(max_length=32)
    notes = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_events",
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.order.order_number}: {self.from_status or 'new'} -> {self.to_status}"
