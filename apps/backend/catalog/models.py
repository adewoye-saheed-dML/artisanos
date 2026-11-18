from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TenantOwnedModel, TimeStampedModel


class Storefront(TimeStampedModel):
    """Public storefront profile for an artisan organization."""

    organization = models.OneToOneField(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="storefront",
    )
    headline = models.CharField(max_length=180, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    whatsapp_number = models.CharField(max_length=32, blank=True, default="")
    instagram_handle = models.CharField(max_length=64, blank=True, default="")
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["organization__name"]

    def __str__(self) -> str:
        return f"Storefront: {self.organization.name} (/{self.organization.slug})"


class Product(TenantOwnedModel):
    """Organization-scoped ready-made product, made-to-order garment, or service listing."""

    class ProductType(models.TextChoices):
        READY_MADE = "ready_made", "Ready-Made"
        MADE_TO_ORDER = "made_to_order", "Made to Order"
        SERVICE = "service", "Service Listing"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=160, db_index=True)
    slug = models.SlugField(max_length=180)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=64, blank=True, default="Bespoke Tailoring")
    product_type = models.CharField(
        max_length=24,
        choices=ProductType.choices,
        default=ProductType.MADE_TO_ORDER,
        db_index=True,
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="NGN")
    image_url = models.CharField(max_length=500, blank=True, default="")
    sku = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    track_inventory = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("organization", "slug")]
        indexes = [
            models.Index(fields=["organization", "status", "product_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.organization.name})"


class ProductVariant(TenantOwnedModel):
    """Optional size/color variant for a product."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    name = models.CharField(max_length=80)
    sku = models.CharField(max_length=64, blank=True, default="")
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("product", "name")]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.name}"


class InventoryMovement(TenantOwnedModel):
    """Immutable audit log of every stock quantity adjustment."""

    class MovementType(models.TextChoices):
        INITIAL = "initial", "Initial Stock"
        RESTOCK = "restock", "Restock"
        SALE = "sale", "Sale"
        ADJUSTMENT = "adjustment", "Manual Adjustment"
        RETURN = "return", "Customer Return"
        DAMAGE = "damage", "Damage / Write-off"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory_movements",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )
    movement_type = models.CharField(max_length=24, choices=MovementType.choices)
    quantity_delta = models.IntegerField()
    balance_after = models.IntegerField()
    reason = models.CharField(max_length=255, blank=True, default="")
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_movements",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "product", "created_at"]),
        ]

    def __str__(self) -> str:
        sign = "+" if self.quantity_delta >= 0 else ""
        return f"{self.product.name}: {sign}{self.quantity_delta} -> {self.balance_after}"


class StorefrontInquiry(TenantOwnedModel):
    """Public buyer inquiry submitted via an artisan's public storefront."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CONVERTED = "converted", "Converted to Order"
        CLOSED = "closed", "Closed"

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inquiries",
    )
    buyer_name = models.CharField(max_length=150)
    buyer_phone = models.CharField(max_length=32)
    buyer_email = models.EmailField(blank=True, default="")
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Inquiry from {self.buyer_name} ({self.organization.name})"
