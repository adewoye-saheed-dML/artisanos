import uuid

from django.db import transaction
from django.utils.text import slugify
from rest_framework import exceptions

from notifications.models import Notification
from notifications.services import create_notification

from .models import InventoryMovement, Product, ProductVariant, Storefront, StorefrontInquiry


def get_or_create_storefront(organization) -> Storefront:
    storefront, _ = Storefront.objects.get_or_create(
        organization=organization,
        defaults={
            "headline": f"Bespoke craft by {organization.name}",
            "bio": "",
            "whatsapp_number": organization.phone or "",
            "is_published": True,
        },
    )
    return storefront


def generate_unique_product_slug(organization, name: str) -> str:
    base = slugify(name)[:140] or "product"
    candidate = base
    while Product.objects.filter(organization=organization, slug=candidate).exists():
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    return candidate


@transaction.atomic
def create_product_with_initial_stock(*, organization, created_by, validated_data: dict) -> Product:
    from billing.services import enforce_plan_limit

    enforce_plan_limit(organization, "products")
    initial_stock = validated_data.pop("initial_stock", 0)
    product_type = validated_data.get("product_type", Product.ProductType.MADE_TO_ORDER)
    track_inventory = validated_data.get(
        "track_inventory",
        product_type == Product.ProductType.READY_MADE,
    )
    if initial_stock < 0:
        raise exceptions.ValidationError({"initial_stock": "Initial stock cannot be negative."})

    product = Product.objects.create(
        organization=organization,
        slug=generate_unique_product_slug(organization, validated_data["name"]),
        name=validated_data["name"].strip(),
        description=validated_data.get("description", "").strip(),
        category=validated_data.get("category", "Bespoke Tailoring").strip() or "Bespoke Tailoring",
        product_type=product_type,
        price=validated_data["price"],
        currency=validated_data.get("currency", organization.currency).upper(),
        image_url=validated_data.get("image_url", "").strip(),
        sku=validated_data.get("sku", "").strip(),
        status=validated_data.get("status", Product.Status.DRAFT),
        track_inventory=track_inventory,
        stock_quantity=initial_stock if track_inventory else 0,
        created_by=created_by,
    )

    if track_inventory and initial_stock > 0:
        InventoryMovement.objects.create(
            organization=organization,
            product=product,
            movement_type=InventoryMovement.MovementType.INITIAL,
            quantity_delta=initial_stock,
            balance_after=initial_stock,
            reason="Initial stock recorded at product creation.",
            performed_by=created_by,
        )
    return product


@transaction.atomic
def adjust_inventory(
    *,
    organization,
    product: Product,
    movement_type: str,
    quantity_delta: int,
    reason: str,
    performed_by,
    variant: ProductVariant | None = None,
) -> InventoryMovement:
    """
    Atomically adjust product (or variant) stock and record an immutable InventoryMovement.
    Prevents silent stock overwrites and rejects negative balances.
    """
    if product.organization_id != organization.id:
        raise exceptions.PermissionDenied("Product does not belong to the active organization.")
    if not product.track_inventory:
        raise exceptions.ValidationError("Inventory tracking is disabled for this listing.")
    if quantity_delta == 0:
        raise exceptions.ValidationError({"quantity_delta": "Quantity change cannot be zero."})

    locked_product = Product.objects.select_for_update().get(id=product.id)

    if variant is not None:
        if variant.organization_id != organization.id or variant.product_id != product.id:
            raise exceptions.ValidationError({"variant": "Variant does not belong to this product."})
        locked_variant = ProductVariant.objects.select_for_update().get(id=variant.id)
        new_variant_balance = locked_variant.stock_quantity + quantity_delta
        if new_variant_balance < 0:
            raise exceptions.ValidationError(
                {"quantity_delta": f"Insufficient variant stock (available: {locked_variant.stock_quantity})."}
            )
        locked_variant.stock_quantity = new_variant_balance
        locked_variant.save(update_fields=["stock_quantity", "updated_at"])

    new_balance = locked_product.stock_quantity + quantity_delta
    if new_balance < 0:
        raise exceptions.ValidationError(
            {"quantity_delta": f"Insufficient stock (available: {locked_product.stock_quantity})."}
        )

    locked_product.stock_quantity = new_balance
    locked_product.save(update_fields=["stock_quantity", "updated_at"])

    movement = InventoryMovement.objects.create(
        organization=organization,
        product=locked_product,
        variant=variant,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        balance_after=new_balance,
        reason=reason.strip(),
        performed_by=performed_by,
    )

    if (
        locked_product.product_type == Product.ProductType.READY_MADE
        and quantity_delta < 0
        and new_balance <= 2
    ):
        create_notification(
            organization=organization,
            event_type=Notification.EventType.LOW_STOCK,
            title=f"Low stock: {locked_product.name}",
            message=f"Remaining stock is {new_balance} after {movement_type}.",
            link_path="/products",
        )

    return movement


@transaction.atomic
def submit_storefront_inquiry(
    *,
    organization,
    buyer_name: str,
    buyer_phone: str,
    message: str,
    buyer_email: str = "",
    product: Product | None = None,
) -> StorefrontInquiry:
    if product is not None:
        if product.organization_id != organization.id or product.status != Product.Status.PUBLISHED:
            raise exceptions.ValidationError({"product": "Selected product is not available on this storefront."})

    inquiry = StorefrontInquiry.objects.create(
        organization=organization,
        product=product,
        buyer_name=buyer_name.strip(),
        buyer_phone=buyer_phone.strip(),
        buyer_email=buyer_email.strip(),
        message=message.strip(),
        status=StorefrontInquiry.Status.NEW,
    )

    subject = f" for {product.name}" if product else ""
    create_notification(
        organization=organization,
        event_type=Notification.EventType.STOREFRONT_INQUIRY,
        title=f"New storefront inquiry{subject}",
        message=f"{inquiry.buyer_name} ({inquiry.buyer_phone}): {inquiry.message[:140]}",
        link_path="/products",
    )
    return inquiry
