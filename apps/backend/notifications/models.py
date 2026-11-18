from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class Notification(TenantOwnedModel):
    """Organization-scoped in-app notification for workshop events."""

    class EventType(models.TextChoices):
        MEASUREMENT_SUBMITTED = "measurement_submitted", "Measurement Submitted"
        ORDER_CONFIRMED = "order_confirmed", "Order Confirmed"
        ORDER_READY = "order_ready", "Order Ready"
        STOREFRONT_INQUIRY = "storefront_inquiry", "Storefront Inquiry"
        LOW_STOCK = "low_stock", "Low Stock Alert"
        SYSTEM = "system", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    event_type = models.CharField(
        max_length=32,
        choices=EventType.choices,
        default=EventType.SYSTEM,
        db_index=True,
    )
    title = models.CharField(max_length=160)
    message = models.TextField(blank=True, default="")
    link_path = models.CharField(max_length=255, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_read", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.event_type}] {self.title}"
