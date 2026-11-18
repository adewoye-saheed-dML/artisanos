from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class MeasurementTemplate(TimeStampedModel):
    """
    Configurable measurement template (system-wide when organization is null,
    or custom-owned by an organization).
    """

    class Category(models.TextChoices):
        TAILORING = "tailoring", "Tailoring"
        SHOEMAKING = "shoemaking", "Shoemaking"
        LEATHERWORK = "leatherwork", "Leatherwork"
        OTHER = "other", "Other"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_measurement_templates",
        db_index=True,
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.TAILORING)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                condition=Q(organization__isnull=False),
                name="uniq_org_template_slug",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(organization__isnull=True),
                name="uniq_system_template_slug",
            ),
        ]

    @property
    def is_system(self) -> bool:
        return self.organization_id is None

    def __str__(self) -> str:
        scope = "System" if self.is_system else self.organization.name
        return f"{self.name} [{scope}]"


class MeasurementTemplateVersion(TimeStampedModel):
    """Immutable published version of a measurement template."""

    template = models.ForeignKey(
        MeasurementTemplate,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    is_published = models.BooleanField(default=True)
    changelog = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_template_versions",
    )

    class Meta:
        unique_together = [("template", "version_number")]
        ordering = ["-version_number"]

    def __str__(self) -> str:
        return f"{self.template.name} v{self.version_number}"


class MeasurementField(TimeStampedModel):
    """Data-driven measurement field definition inside a template version."""

    class UnitType(models.TextChoices):
        CIRCUMFERENCE = "circumference", "Circumference"
        LENGTH = "length", "Length"
        WIDTH = "width", "Width"
        ANGLE = "angle", "Angle"
        NUMERIC = "numeric", "Numeric"
        TEXT = "text", "Text"

    class DefaultUnit(models.TextChoices):
        CM = "cm", "cm"
        IN = "in", "in"
        DEG = "deg", "deg"
        NONE = "none", "none"

    template_version = models.ForeignKey(
        MeasurementTemplateVersion,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    key = models.SlugField(max_length=64)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    unit_type = models.CharField(max_length=24, choices=UnitType.choices, default=UnitType.LENGTH)
    default_unit = models.CharField(max_length=10, choices=DefaultUnit.choices, default=DefaultUnit.CM)
    min_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_required = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    guidance_text = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = [("template_version", "key")]
        ordering = ["display_order", "label"]

    def __str__(self) -> str:
        return f"{self.label} ({self.key})"
