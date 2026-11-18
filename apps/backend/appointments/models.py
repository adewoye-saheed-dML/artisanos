from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class Appointment(TenantOwnedModel):
    """Customer measurement, fitting, consultation, or collection appointment."""

    class AppointmentType(models.TextChoices):
        MEASUREMENT = "measurement", "Measurement Session"
        FIRST_FITTING = "first_fitting", "First Fitting"
        FINAL_FITTING = "final_fitting", "Final Fitting"
        CONSULTATION = "consultation", "Consultation"
        COLLECTION = "collection", "Order Collection"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    appointment_type = models.CharField(
        max_length=32,
        choices=AppointmentType.choices,
        default=AppointmentType.FIRST_FITTING,
    )
    title = models.CharField(max_length=150)
    scheduled_at = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    location = models.CharField(max_length=180, blank=True, default="Studio")
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_appointments",
    )
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_appointments",
    )

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["organization", "scheduled_at"]),
            models.Index(fields=["organization", "status", "scheduled_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.customer.full_name} @ {self.scheduled_at.isoformat()})"
