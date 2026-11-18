from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel


class ProductionTask(TenantOwnedModel):
    """Checklist task or alteration item attached to a tailoring order."""

    class Stage(models.TextChoices):
        CUTTING = "cutting", "Cutting"
        SEWING = "sewing", "Sewing & Assembly"
        EMBROIDERY = "embroidery", "Embroidery / Detailing"
        FITTING = "fitting", "Fitting Adjustment"
        ALTERATION = "alteration", "Alteration"
        FINISHING = "finishing", "Finishing & Pressing"
        QUALITY_CHECK = "quality_check", "Quality Check"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        BLOCKED = "blocked", "Blocked"
        DONE = "done", "Done"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="production_tasks",
    )
    title = models.CharField(max_length=150)
    stage = models.CharField(max_length=32, choices=Stage.choices, default=Stage.SEWING)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.TODO, db_index=True)
    is_alteration = models.BooleanField(default=False, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_production_tasks",
    )
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_production_tasks",
    )

    class Meta:
        ordering = ["display_order", "created_at"]
        indexes = [
            models.Index(fields=["organization", "order", "status"]),
            models.Index(fields=["organization", "assigned_to", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.order.order_number}: {self.title} ({self.status})"
