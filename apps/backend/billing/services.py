import hashlib
import hmac
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from catalog.models import Product
from customers.models import Customer
from measurements.models import MeasurementRequest
from organizations.models import Membership, Organization

from .models import AuditLog, PaymentTransaction, Plan, Subscription
from .seed import seed_default_plans


def get_or_create_subscription(organization: Organization) -> Subscription:
    """Return the organization's subscription, provisioning Starter plan if none exists."""
    sub = Subscription.objects.select_related("plan").filter(organization=organization).first()
    if sub:
        return sub
    plans = seed_default_plans()
    starter = plans["starter"]
    return Subscription.objects.create(
        organization=organization,
        plan=starter,
        status=Subscription.Status.ACTIVE,
        provider=Subscription.Provider.MANUAL,
        current_period_start=timezone.now(),
        current_period_end=None,
    )


def get_workspace_usage_summary(organization: Organization) -> dict:
    """Compute real database usage counts against active subscription entitlements."""
    sub = get_or_create_subscription(organization)
    plan = sub.plan
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    members_used = Membership.objects.filter(
        organization=organization,
        status=Membership.Status.ACTIVE,
    ).count()
    customers_used = Customer.objects.filter(
        organization=organization,
        is_archived=False,
    ).count()
    monthly_requests_used = MeasurementRequest.objects.filter(
        organization=organization,
        created_at__gte=month_start,
    ).count()
    products_used = Product.objects.filter(
        organization=organization,
    ).exclude(status=Product.Status.ARCHIVED).count()

    return {
        "members": {"used": members_used, "limit": plan.max_members},
        "customers": {"used": customers_used, "limit": plan.max_customers},
        "monthly_measurement_requests": {
            "used": monthly_requests_used,
            "limit": plan.max_monthly_measurement_requests,
        },
        "products": {"used": products_used, "limit": plan.max_products},
    }


def enforce_plan_limit(organization: Organization, metric: str) -> None:
    """Enforce server-side subscription usage limit before creating a metered resource."""
    usage = get_workspace_usage_summary(organization)
    if metric not in usage:
        return
    entry = usage[metric]
    if entry["used"] >= entry["limit"]:
        sub = get_or_create_subscription(organization)
        raise exceptions.PermissionDenied(
            f"Plan limit reached for '{metric}' ({entry['used']}/{entry['limit']} on {sub.plan.name} plan). "
            "Upgrade your subscription plan to add more."
        )


@transaction.atomic
def initiate_plan_checkout(*, organization: Organization, plan: Plan, actor) -> PaymentTransaction:
    """
    Create a pending billing transaction for a plan upgrade.
    Free plan switches apply immediately; paid plans remain pending until verified
    via Paystack webhook or platform admin.
    """
    sub = get_or_create_subscription(organization)
    if not plan.is_active:
        raise exceptions.ValidationError({"plan": "Selected plan is not active."})

    reference = f"ART-{timezone.now().strftime('%Y%m%d')}-{secrets.token_hex(6).upper()}"

    if plan.monthly_price <= Decimal("0.00"):
        tx = PaymentTransaction.objects.create(
            organization=organization,
            subscription=sub,
            plan=plan,
            reference=reference,
            provider="manual",
            amount=Decimal("0.00"),
            currency=plan.currency,
            status=PaymentTransaction.Status.SUCCEEDED,
            verified_at=timezone.now(),
            initiated_by=actor,
        )
        old_plan = sub.plan.code
        sub.plan = plan
        sub.status = Subscription.Status.ACTIVE
        sub.provider = Subscription.Provider.MANUAL
        sub.current_period_start = timezone.now()
        sub.current_period_end = None
        sub.save()
        AuditLog.objects.create(
            organization=organization,
            actor=actor,
            action="plan_changed",
            target_type="Subscription",
            target_id=str(sub.id),
            reason=f"Switched from {old_plan} to {plan.code}.",
            metadata={"reference": reference},
        )
        return tx

    return PaymentTransaction.objects.create(
        organization=organization,
        subscription=sub,
        plan=plan,
        reference=reference,
        provider="paystack",
        amount=plan.monthly_price,
        currency=plan.currency,
        status=PaymentTransaction.Status.PENDING,
        initiated_by=actor,
    )


def verify_paystack_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify Paystack X-Paystack-Signature using constant-time HMAC-SHA512."""
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "") or ""
    if not secret or not signature_header:
        return False
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature_header.strip())


@transaction.atomic
def process_paystack_webhook_event(payload: dict) -> dict:
    """
    Idempotently verify and apply a Paystack webhook event (charge.success).
    Never trusts frontend payment callbacks; validates amount and currency against
    the server-side PaymentTransaction record.
    """
    event = payload.get("event")
    data = payload.get("data") or {}
    reference = data.get("reference")

    if event != "charge.success" or not reference:
        return {"processed": False, "detail": "Ignored non-charge.success event."}

    # Handle customer Escrow funding references (ESC-...)
    if str(reference).startswith("ESC-"):
        from escrow.models import EscrowTransaction
        from escrow.services import fund_escrow_transaction

        escrow = (
            EscrowTransaction.objects.select_for_update(of=("self",))
            .select_related("organization")
            .filter(reference=reference)
            .first()
        )
        if not escrow:
            raise exceptions.NotFound("Escrow transaction reference not found.")
        if escrow.status == EscrowTransaction.Status.FUNDED_HELD:
            return {"processed": True, "detail": "Escrow already funded (idempotent)."}

        paid_minor = data.get("amount")
        paid_currency = (data.get("currency") or "").upper()
        expected_minor = int((escrow.total_amount * Decimal("100")).quantize(Decimal("1")))
        if paid_minor != expected_minor or paid_currency != escrow.currency.upper():
            raise exceptions.ValidationError("Webhook escrow payment amount or currency mismatch.")

        fund_escrow_transaction(escrow=escrow, actor=None, via_webhook=True, provider_payload=payload)
        return {"processed": True, "detail": f"Funded escrow {escrow.reference}."}

    tx = (
        PaymentTransaction.objects.select_for_update(of=("self",))
        .select_related("organization", "subscription", "plan")
        .filter(reference=reference)
        .first()
    )
    if not tx:
        raise exceptions.NotFound("Payment transaction reference not found.")

    if tx.status == PaymentTransaction.Status.SUCCEEDED:
        return {"processed": True, "detail": "Already verified (idempotent)."}

    # Paystack amounts are in minor units (kobo = NGN * 100)
    paid_minor = data.get("amount")
    paid_currency = (data.get("currency") or "").upper()
    expected_minor = int((tx.amount * Decimal("100")).quantize(Decimal("1")))
    if paid_minor != expected_minor or paid_currency != tx.currency.upper():
        tx.status = PaymentTransaction.Status.FAILED
        tx.provider_payload = payload
        tx.save(update_fields=["status", "provider_payload", "updated_at"])
        raise exceptions.ValidationError("Webhook payment amount or currency mismatch.")

    now = timezone.now()
    tx.status = PaymentTransaction.Status.SUCCEEDED
    tx.provider_payload = payload
    tx.verified_at = now
    tx.save(update_fields=["status", "provider_payload", "verified_at", "updated_at"])

    sub = tx.subscription or get_or_create_subscription(tx.organization)
    if tx.plan:
        sub.plan = tx.plan
    sub.status = Subscription.Status.ACTIVE
    sub.provider = Subscription.Provider.PAYSTACK
    sub.provider_reference = reference
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(days=30)
    sub.save()

    AuditLog.objects.create(
        organization=tx.organization,
        actor=None,
        action="payment_verified",
        target_type="PaymentTransaction",
        target_id=str(tx.id),
        reason=f"Paystack webhook verified payment for plan '{sub.plan.code}'.",
        metadata={"reference": reference, "amount": str(tx.amount), "currency": tx.currency},
    )
    return {"processed": True, "detail": f"Upgraded {tx.organization.name} to {sub.plan.name}."}
