from decimal import Decimal
import uuid

from django.db import transaction
from django.utils.text import slugify
from rest_framework import exceptions

from customers.models import Customer
from locations.utils import haversine_km
from notifications.models import Notification
from notifications.services import create_notification
from orders.models import Order
from orders.services import create_order

from .models import InventoryMovement, Product, ProductVariant, Storefront, StorefrontInquiry


def get_or_create_storefront(organization) -> Storefront:
    storefront, _ = Storefront.objects.get_or_create(
        organization=organization,
        defaults={
            "headline": f"{organization.get_category_display()} by {organization.name}",
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
    inquiry_type: str | None = None,
    urgency: str = StorefrontInquiry.Urgency.NORMAL,
    customer_ward=None,
    customer_polling_unit=None,
    customer_address: str = "",
    preferred_date=None,
    quantity: int = 1,
    budget_amount: Decimal | None = None,
) -> StorefrontInquiry:
    if product is not None:
        if product.organization_id != organization.id or product.status != Product.Status.PUBLISHED:
            raise exceptions.ValidationError({"product": "Selected product is not available on this storefront."})

    if customer_polling_unit is not None:
        if customer_ward is not None and customer_polling_unit.ward_id != customer_ward.id:
            raise exceptions.ValidationError(
                {"customer_polling_unit": "Selected polling unit does not belong to the chosen ward."}
            )
        customer_ward = customer_polling_unit.ward

    resolved_type = inquiry_type
    if not resolved_type:
        if product is not None:
            resolved_type = (
                StorefrontInquiry.InquiryType.SERVICE_BOOKING
                if product.product_type == Product.ProductType.SERVICE
                else StorefrontInquiry.InquiryType.PRODUCT_ORDER
            )
        else:
            resolved_type = StorefrontInquiry.InquiryType.GENERAL

    inquiry = StorefrontInquiry.objects.create(
        organization=organization,
        product=product,
        inquiry_type=resolved_type,
        urgency=urgency or StorefrontInquiry.Urgency.NORMAL,
        buyer_name=buyer_name.strip(),
        buyer_phone=buyer_phone.strip(),
        buyer_email=buyer_email.strip(),
        customer_ward=customer_ward,
        customer_polling_unit=customer_polling_unit,
        customer_address=customer_address.strip(),
        preferred_date=preferred_date,
        quantity=max(1, int(quantity or 1)),
        budget_amount=budget_amount,
        message=message.strip(),
        status=StorefrontInquiry.Status.NEW,
    )

    if resolved_type == StorefrontInquiry.InquiryType.WORK_CALLOUT:
        loc_hint = (
            customer_polling_unit.name
            if customer_polling_unit
            else (customer_ward.name if customer_ward else customer_address)
        )
        title = (
            f"Urgent work call-out: {inquiry.buyer_name}"
            if urgency == StorefrontInquiry.Urgency.EMERGENCY
            else f"New work call-out from {inquiry.buyer_name}"
        )
        msg_prefix = f"Location: {loc_hint} · " if loc_hint else ""
    else:
        subject = f" for {product.name}" if product else ""
        title = f"New storefront inquiry{subject}"
        msg_prefix = ""

    create_notification(
        organization=organization,
        event_type=Notification.EventType.STOREFRONT_INQUIRY,
        title=title[:160],
        message=f"{msg_prefix}{inquiry.buyer_name} ({inquiry.buyer_phone}): {inquiry.message[:140]}",
        link_path="/products",
    )
    return inquiry


@transaction.atomic
def convert_inquiry_to_order(*, organization, inquiry: StorefrontInquiry, actor) -> Order:
    """Convert an incoming storefront work call-out or product request into a real Customer + Order."""
    if inquiry.organization_id != organization.id:
        raise exceptions.PermissionDenied("Inquiry does not belong to the active organization.")
    if inquiry.converted_order_id:
        raise exceptions.ValidationError("This inquiry has already been converted into an order.")

    location_parts = [
        inquiry.customer_address,
        inquiry.customer_polling_unit.name if inquiry.customer_polling_unit else "",
        inquiry.customer_ward.name if inquiry.customer_ward else "",
    ]
    combined_address = ", ".join([p for p in location_parts if p]).strip()

    customer = Customer.objects.filter(organization=organization, phone=inquiry.buyer_phone).first()
    if not customer:
        customer = Customer.objects.create(
            organization=organization,
            full_name=inquiry.buyer_name,
            phone=inquiry.buyer_phone,
            email=inquiry.buyer_email,
            address=combined_address,
            preferred_contact_method=Customer.ContactMethod.PHONE,
            notes=f"Created from storefront {inquiry.get_inquiry_type_display().lower()}.",
            created_by=actor,
        )

    if inquiry.product:
        service_title = f"{inquiry.product.name} (x{inquiry.quantity})" if inquiry.quantity > 1 else inquiry.product.name
        quoted = (inquiry.product.price * inquiry.quantity).quantize(Decimal("0.01"))
    else:
        service_title = (
            f"On-Site {organization.get_category_display()} Call-Out"
            if inquiry.inquiry_type == StorefrontInquiry.InquiryType.WORK_CALLOUT
            else f"{organization.get_category_display()} Request"
        )
        quoted = (
            inquiry.budget_amount
            if inquiry.budget_amount is not None
            else (organization.callout_fee or Decimal("0.00"))
        )

    order = create_order(
        organization=organization,
        created_by=actor,
        validated_data={
            "customer": customer,
            "garment_type": service_title[:150],
            "description": inquiry.message,
            "quoted_amount": quoted,
            "deposit_amount": Decimal("0.00"),
            "status": Order.Status.QUOTED,
            "expected_completion_date": inquiry.preferred_date,
            "delivery_method": (
                Order.DeliveryMethod.DELIVERY
                if inquiry.inquiry_type == StorefrontInquiry.InquiryType.WORK_CALLOUT
                else Order.DeliveryMethod.PICKUP
            ),
            "customer_instructions": (
                f"Urgency: {inquiry.get_urgency_display()}"
                + (f" | Location: {combined_address}" if combined_address else "")
            ),
        },
    )

    inquiry.status = StorefrontInquiry.Status.CONVERTED
    inquiry.converted_order = order
    inquiry.save(update_fields=["status", "converted_order", "updated_at"])
    return order


def compute_organization_proximity(
    org,
    *,
    target_polling_unit=None,
    target_ward=None,
    target_lga=None,
    target_state=None,
    service_ward_ids: set | None = None,
) -> tuple[int, str, str, float | None]:
    """
    Compute hierarchical proximity rank for an artisan organization relative to a customer's
    selected Nigerian Polling Unit, Ward, LGA, or State.
    Returns (sort_rank, tier_code, human_label, distance_km).
    Lower sort_rank is closer.
    """
    distance_km = None
    if target_polling_unit is not None and org.polling_unit is not None:
        distance_km = haversine_km(
            target_polling_unit.latitude,
            target_polling_unit.longitude,
            org.polling_unit.latitude,
            org.polling_unit.longitude,
        )

    effective_ward = target_ward or (target_polling_unit.ward if target_polling_unit else None)
    effective_lga = target_lga or (effective_ward.lga if effective_ward else None)
    effective_state = target_state or (effective_lga.state if effective_lga else None)

    if service_ward_ids is None:
        service_ward_ids = {w.id for w in org.service_wards.all()}

    if target_polling_unit is not None and org.polling_unit_id == target_polling_unit.id:
        return (1, "same_polling_unit", "At your Polling Unit", 0.0 if distance_km is None else distance_km)

    if effective_ward is not None and org.ward_id == effective_ward.id:
        return (2, "same_ward", "In your Ward", distance_km)

    if effective_ward is not None and effective_ward.id in service_ward_ids:
        return (3, "covers_ward", "Covers your Ward", distance_km)

    if effective_lga is not None and org.lga_id == effective_lga.id:
        return (4, "same_lga", "Nearby in your LGA", distance_km)

    if effective_state is not None and org.state_id == effective_state.id:
        return (5, "same_state", "Same State", distance_km)

    return (6, "national", "Nationwide", distance_km)
