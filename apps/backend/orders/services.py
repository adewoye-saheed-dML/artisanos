from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from measurements.models import MeasurementProfile
from organizations.models import Membership

from .models import Order, OrderStatusEvent

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Order.Status.DRAFT: {
        Order.Status.AWAITING_MEASUREMENTS,
        Order.Status.QUOTED,
        Order.Status.CONFIRMED,
        Order.Status.ON_HOLD,
        Order.Status.CANCELLED,
    },
    Order.Status.AWAITING_MEASUREMENTS: {
        Order.Status.QUOTED,
        Order.Status.CONFIRMED,
        Order.Status.ON_HOLD,
        Order.Status.CANCELLED,
    },
    Order.Status.QUOTED: {
        Order.Status.AWAITING_MEASUREMENTS,
        Order.Status.CONFIRMED,
        Order.Status.ON_HOLD,
        Order.Status.CANCELLED,
    },
    Order.Status.CONFIRMED: {
        Order.Status.IN_PRODUCTION,
        Order.Status.ON_HOLD,
        Order.Status.CANCELLED,
    },
    Order.Status.IN_PRODUCTION: {
        Order.Status.FITTING,
        Order.Status.READY,
        Order.Status.ON_HOLD,
        Order.Status.CANCELLED,
    },
    Order.Status.FITTING: {
        Order.Status.IN_PRODUCTION,
        Order.Status.READY,
        Order.Status.ON_HOLD,
        Order.Status.CANCELLED,
    },
    Order.Status.READY: {
        Order.Status.COMPLETED,
        Order.Status.FITTING,
        Order.Status.ON_HOLD,
    },
    Order.Status.ON_HOLD: {
        Order.Status.AWAITING_MEASUREMENTS,
        Order.Status.QUOTED,
        Order.Status.CONFIRMED,
        Order.Status.IN_PRODUCTION,
        Order.Status.FITTING,
        Order.Status.READY,
        Order.Status.CANCELLED,
    },
    Order.Status.COMPLETED: set(),
    Order.Status.CANCELLED: set(),
}


def compute_payment_status(
    quoted_amount: Decimal,
    agreed_amount: Decimal | None,
    deposit_amount: Decimal,
) -> str:
    total = agreed_amount if agreed_amount is not None else quoted_amount
    if deposit_amount <= Decimal("0.00"):
        return Order.PaymentStatus.UNPAID
    if total > Decimal("0.00") and deposit_amount >= total:
        return Order.PaymentStatus.PAID
    return Order.PaymentStatus.PARTIAL


def build_measurement_snapshot(profile: MeasurementProfile | None) -> dict | None:
    if profile is None:
        return None
    values = [
        {
            "field_key": v.field.key,
            "field_label": v.field.label,
            "numeric_value": str(v.numeric_value) if v.numeric_value is not None else None,
            "text_value": v.text_value,
            "unit": v.unit,
        }
        for v in profile.values.select_related("field").order_by("field__display_order", "field__label")
    ]
    return {
        "profile_id": str(profile.id),
        "version_number": profile.version_number,
        "label": profile.label,
        "template_name": profile.template_version.template.name,
        "template_version_number": profile.template_version.version_number,
        "unit_system": profile.unit_system,
        "status": profile.status,
        "measured_at": profile.measured_at.isoformat(),
        "captured_at": timezone.now().isoformat(),
        "values": values,
    }


def _generate_order_number(organization) -> str:
    year = timezone.now().year
    prefix = f"ORD-{year}-"
    existing_count = Order.objects.filter(
        organization=organization,
        order_number__startswith=prefix,
    ).count()
    seq = existing_count + 1
    candidate = f"{prefix}{seq:04d}"
    while Order.objects.filter(organization=organization, order_number=candidate).exists():
        seq += 1
        candidate = f"{prefix}{seq:04d}"
    return candidate


def _validate_order_relations(*, organization, customer, measurement_profile, assigned_to):
    if customer.organization_id != organization.id:
        raise exceptions.PermissionDenied("Customer does not belong to the active organization.")
    if measurement_profile is not None:
        if measurement_profile.organization_id != organization.id:
            raise exceptions.PermissionDenied("Measurement profile does not belong to the active organization.")
        if measurement_profile.customer_id != customer.id:
            raise exceptions.ValidationError(
                {"measurement_profile": "Measurement profile must belong to the selected customer."}
            )
    if assigned_to is not None:
        is_member = Membership.objects.filter(
            organization=organization,
            user=assigned_to,
            status=Membership.Status.ACTIVE,
        ).exists()
        if not is_member:
            raise exceptions.ValidationError(
                {"assigned_to": "Assigned user must be an active member of this organization."}
            )


@transaction.atomic
def create_order(*, organization, created_by, validated_data: dict) -> Order:
    customer = validated_data["customer"]
    measurement_profile = validated_data.get("measurement_profile")
    assigned_to = validated_data.get("assigned_to")
    _validate_order_relations(
        organization=organization,
        customer=customer,
        measurement_profile=measurement_profile,
        assigned_to=assigned_to,
    )

    initial_status = validated_data.get("status", Order.Status.DRAFT)
    if initial_status not in {
        Order.Status.DRAFT,
        Order.Status.AWAITING_MEASUREMENTS,
        Order.Status.QUOTED,
        Order.Status.CONFIRMED,
    }:
        raise exceptions.ValidationError(
            {"status": "New orders can only start in draft, awaiting_measurements, quoted, or confirmed status."}
        )

    quoted_amount = validated_data.get("quoted_amount", Decimal("0.00"))
    agreed_amount = validated_data.get("agreed_amount")
    deposit_amount = validated_data.get("deposit_amount", Decimal("0.00"))
    payment_status = compute_payment_status(quoted_amount, agreed_amount, deposit_amount)

    snapshot = build_measurement_snapshot(measurement_profile) if measurement_profile else None

    order = Order.objects.create(
        organization=organization,
        customer=customer,
        order_number=_generate_order_number(organization),
        garment_type=validated_data["garment_type"].strip(),
        description=validated_data.get("description", "").strip(),
        measurement_profile=measurement_profile,
        measurement_snapshot=snapshot,
        status=initial_status,
        quoted_amount=quoted_amount,
        agreed_amount=agreed_amount,
        deposit_amount=deposit_amount,
        currency=validated_data.get("currency", organization.currency).upper(),
        payment_status=payment_status,
        expected_completion_date=validated_data.get("expected_completion_date"),
        assigned_to=assigned_to,
        category_options=validated_data.get("category_options") or {},
        customer_instructions=validated_data.get("customer_instructions", "").strip(),
        internal_notes=validated_data.get("internal_notes", "").strip(),
        delivery_method=validated_data.get("delivery_method", Order.DeliveryMethod.PICKUP),
        created_by=created_by,
    )

    OrderStatusEvent.objects.create(
        organization=organization,
        order=order,
        from_status="",
        to_status=order.status,
        notes="Order created.",
        changed_by=created_by,
    )
    return order


@transaction.atomic
def transition_order_status(*, order: Order, to_status: str, actor, notes: str = "") -> Order:
    """Validate and apply an order status transition with an audit event."""
    if to_status == order.status:
        raise exceptions.ValidationError({"to_status": f"Order is already in '{to_status}' status."})

    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if to_status not in allowed:
        raise exceptions.ValidationError(
            {
                "to_status": (
                    f"Cannot transition order from '{order.status}' to '{to_status}'. "
                    f"Allowed next statuses: {', '.join(sorted(allowed)) or 'none (terminal status)'}."
                )
            }
        )

    from_status = order.status
    order.status = to_status

    update_fields = ["status", "updated_at"]
    # Refresh and freeze snapshot when confirming an order with a linked measurement profile
    if to_status == Order.Status.CONFIRMED and order.measurement_profile is not None:
        order.measurement_snapshot = build_measurement_snapshot(order.measurement_profile)
        update_fields.append("measurement_snapshot")

    order.save(update_fields=update_fields)

    OrderStatusEvent.objects.create(
        organization=order.organization,
        order=order,
        from_status=from_status,
        to_status=to_status,
        notes=notes.strip(),
        changed_by=actor,
    )

    if to_status in {Order.Status.CONFIRMED, Order.Status.READY}:
        from notifications.models import Notification
        from notifications.services import create_notification

        event_type = (
            Notification.EventType.ORDER_CONFIRMED
            if to_status == Order.Status.CONFIRMED
            else Notification.EventType.ORDER_READY
        )
        label = "confirmed" if to_status == Order.Status.CONFIRMED else "ready for collection"
        create_notification(
            organization=order.organization,
            event_type=event_type,
            title=f"{order.order_number} {label}",
            message=f"{order.garment_type} for {order.customer.full_name} is now {label}.",
            link_path=f"/orders/{order.id}",
        )
    return order
