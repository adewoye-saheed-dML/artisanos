from django.db import models

from core.models import TimeStampedModel


class NigerianState(TimeStampedModel):
    """Nigerian State or Federal Capital Territory (36 States + FCT Abuja)."""

    name = models.CharField(max_length=80, unique=True, db_index=True)
    code = models.CharField(max_length=10, unique=True, db_index=True)
    geopolitical_zone = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class NigerianLGA(TimeStampedModel):
    """Local Government Area within a Nigerian State."""

    state = models.ForeignKey(
        NigerianState,
        on_delete=models.CASCADE,
        related_name="lgas",
    )
    name = models.CharField(max_length=120, db_index=True)
    code = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        ordering = ["name"]
        unique_together = [("state", "name")]
        indexes = [
            models.Index(fields=["state", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name}, {self.state.name}"


class NigerianWard(TimeStampedModel):
    """INEC Registration Area / Electoral Ward within an LGA."""

    class DataSource(models.TextChoices):
        INEC = "inec", "Official INEC"
        GRID3 = "grid3", "GRID3 Operational Boundary"
        SEED = "seed", "Seeded Baseline"
        COMMUNITY = "community", "Community Mapped"

    lga = models.ForeignKey(
        NigerianLGA,
        on_delete=models.CASCADE,
        related_name="wards",
    )
    name = models.CharField(max_length=150, db_index=True)
    code = models.CharField(max_length=16, blank=True, default="")
    alt_names = models.CharField(max_length=300, blank=True, default="")
    data_source = models.CharField(
        max_length=24,
        choices=DataSource.choices,
        default=DataSource.INEC,
        db_index=True,
    )

    class Meta:
        ordering = ["name"]
        unique_together = [("lga", "name")]
        indexes = [
            models.Index(fields=["lga", "name"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.lga.name})"


class PollingUnit(TimeStampedModel):
    """Hyper-local INEC Polling Unit inside a Nigerian Ward (scales to all 176,846 official INEC PUs)."""

    class DataSource(models.TextChoices):
        INEC = "inec", "Official INEC"
        GRID3 = "grid3", "GRID3 Operational"
        SEED = "seed", "Seeded Baseline"
        COMMUNITY = "community", "Community Mapped"

    ward = models.ForeignKey(
        NigerianWard,
        on_delete=models.CASCADE,
        related_name="polling_units",
    )
    name = models.CharField(max_length=300, db_index=True)
    pu_code = models.CharField(max_length=48, unique=True, db_index=True)
    landmark = models.CharField(max_length=300, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    data_source = models.CharField(
        max_length=24,
        choices=DataSource.choices,
        default=DataSource.INEC,
        db_index=True,
    )

    class Meta:
        ordering = ["pu_code", "name"]
        indexes = [
            models.Index(fields=["ward", "name"]),
            models.Index(fields=["latitude", "longitude"], name="loc_pu_lat_lng_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} [{self.pu_code}]"
