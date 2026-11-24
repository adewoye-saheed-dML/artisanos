import hashlib
import hmac
import secrets
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import exceptions

from catalog.models import Product
from customers.models import Customer
from measurements.models import MeasurementRequest
from organizations.models import Membership, Organization

from .models import AuditLog, MarketplaceBoost, PaymentTransaction, Plan, Subscription
from .paystack import initialize_paystack_transaction, verify_paystack_transaction
from .seed import seed_default_plans

# Standardized Nigeria-calibrated Spotlight Boost packages (Jiji-style immediate cash flow)
BOOST_PACKAGES: dict[str, dict] = {
    MarketplaceBoost.BoostType.AREA_7D: {
        "code": MarketplaceBoost.BoostType.AREA_7D,
        "name": "7-Day Area Spotlight",
        "description": "Pin your workshop to the top Featured slots in your neighborhood & LGA for 7 days.",
        "amount": Decimal("2000.00"),
        "currency": "NGN",
        "duration_days": 7,
        "scope": "storefront",
        "badge_label": "Featured Nearby",
        "eligible_for_plan_credit": True,
    },
    MarketplaceBoost.BoostType.LGA_30D: {
        "code": MarketplaceBoost.BoostType.LGA_30D,
        "name": "30-Day LGA Top Spotlight",
        "description": "Stand out at the top across your entire LGA for 30 days with a Top Spotlight badge.",
        "amount": Decimal("6000.00"),
        "currency": "NGN",
        "duration_days": 30,
        "scope": "storefront",
        "badge_label": "Top Spotlight",
        "eligible_for_plan_credit": False,
    },
    MarketplaceBoost.BoostType.PRODUCT_7D: {
        "code": MarketplaceBoost.BoostType.PRODUCT_7D,
        "name": "7-Day Product / Service Boost",
        "description": "Feature a specific handcrafted item or service at the top of marketplace search for 7 days.",
        "amount": Decimal("1000.00"),
        "currency": "NGN",
        "duration_days": 7,
        "scope": "product",
        "badge_label": "Featured Listing",
        "eligible_for_plan_credit": True,
    },
}


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
        billing_cycle=Subscription.BillingCycle.MONTHLY,
        provider=Subscription.Provider.MANUAL,
        current_period_start=timezone.now(),
        current_period_end=None,
    )


def get_monthly_boost_credit_usage(organization: Organization) -> tuple[int, int]:
    """Return (used_this_month, plan_limit) for included monthly spotlight boost credits."""
    sub = get_or_create_subscription(organization)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = MarketplaceBoost.objects.filter(
        organization=organization,
        used_plan_credit=True,
        created_at__gte=month_start,
    ).exclude(status=MarketplaceBoost.Status.CANCELLED).count()
    return used, sub.plan.monthly_free_boosts


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
    covered_ids = {w.id for w in organization.service_wards.all()}
    if organization.ward_id:
        covered_ids.add(organization.ward_id)
    service_wards_used = len(covered_ids)
    boost_credits_used, boost_credits_limit = get_monthly_boost_credit_usage(organization)

    return {
        "members": {"used": members_used, "limit": plan.max_members},
        "customers": {"used": customers_used, "limit": plan.max_customers},
        "monthly_measurement_requests": {
            "used": monthly_requests_used,
            "limit": plan.max_monthly_measurement_requests,
        },
        "products": {"used": products_used, "limit": plan.max_products},
        "service_wards": {"used": service_wards_used, "limit": plan.max_service_wards},
        "monthly_boost_credits": {"used": boost_credits_used, "limit": boost_credits_limit},
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


def _default_billing_callback_url() -> str:
    site = getattr(settings, "FRONTEND_SITE_URL", "http://localhost:3000").rstrip("/")
    return f"{site}/billing"


def _resolve_safe_callback_url(callback_url: str, default_url: str) -> str:
    """Validate optional client callback_url stays on a trusted frontend origin (prevents open redirect)."""
    cleaned = (callback_url or "").strip()
    if not cleaned:
        return default_url
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise exceptions.ValidationError({"callback_url": "Invalid callback URL."})
    trusted_origins = {
        urlparse(getattr(settings, "FRONTEND_SITE_URL", "http://localhost:3000")).netloc.lower(),
        *(urlparse(o).netloc.lower() for o in getattr(settings, "CORS_ALLOWED_ORIGINS", [])),
    }
    trusted_origins.discard("")
    if parsed.netloc.lower() not in trusted_origins:
        raise exceptions.ValidationError(
            {"callback_url": "Callback URL must belong to a trusted ArtisanOS frontend origin."}
        )
    return cleaned


@transaction.atomic
def initiate_plan_checkout(
    *,
    organization: Organization,
    plan: Plan,
    actor,
    billing_cycle: str = Subscription.BillingCycle.MONTHLY,
    callback_url: str = "",
) -> PaymentTransaction:
    """
    Create a billing transaction for a monthly or annual plan upgrade.
    Free plan switches apply immediately; paid plans initialize Paystack Hosted Checkout when configured
    and activate strictly after Paystack webhook or server-side Paystack verify confirmation.
    """
    sub = get_or_create_subscription(organization)
    if not plan.is_active:
        raise exceptions.ValidationError({"plan": "Selected plan is not active."})

    cycle = (
        Subscription.BillingCycle.ANNUAL
        if billing_cycle == Subscription.BillingCycle.ANNUAL
        else Subscription.BillingCycle.MONTHLY
    )
    amount = (
        plan.annual_price
        if cycle == Subscription.BillingCycle.ANNUAL and plan.annual_price > Decimal("0.00")
        else plan.monthly_price
    )
    reference = f"ART-{timezone.now().strftime('%Y%m%d')}-{secrets.token_hex(6).upper()}"

    if amount <= Decimal("0.00"):
        tx = PaymentTransaction.objects.create(
            organization=organization,
            subscription=sub,
            plan=plan,
            purpose=PaymentTransaction.Purpose.SUBSCRIPTION,
            billing_cycle=cycle,
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
        sub.billing_cycle = cycle
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
            metadata={"reference": reference, "billing_cycle": cycle},
        )
        return tx

    resolved_callback = _resolve_safe_callback_url(callback_url, _default_billing_callback_url())
    customer_email = (getattr(actor, "email", "") or organization.email or "").strip()
    paystack_init = initialize_paystack_transaction(
        email=customer_email,
        amount=amount,
        reference=reference,
        currency=plan.currency,
        callback_url=resolved_callback,
        metadata={
            "purpose": "subscription",
            "organization_id": str(organization.id),
            "plan_code": plan.code,
            "billing_cycle": cycle,
        },
    )

    return PaymentTransaction.objects.create(
        organization=organization,
        subscription=sub,
        plan=plan,
        purpose=PaymentTransaction.Purpose.SUBSCRIPTION,
        billing_cycle=cycle,
        reference=reference,
        provider="paystack",
        amount=amount,
        currency=plan.currency,
        status=PaymentTransaction.Status.PENDING,
        authorization_url=(paystack_init.get("authorization_url", "") if paystack_init else ""),
        access_code=(paystack_init.get("access_code", "") if paystack_init else ""),
        initiated_by=actor,
    )


@transaction.atomic
def initiate_boost_checkout(
    *,
    organization: Organization,
    boost_type: str,
    actor,
    product: Product | None = None,
    use_plan_credit: bool = False,
    callback_url: str = "",
) -> tuple[MarketplaceBoost, PaymentTransaction | None]:
    """
    Create a MarketplaceBoost (Storefront Spotlight or Product/Service Boost).
    If `use_plan_credit=True` and the workspace's active plan has remaining monthly free boost credits,
    the boost activates immediately at ₦0. Otherwise initializes a Paystack transaction (`BST-...`).
    """
    pkg = BOOST_PACKAGES.get(boost_type)
    if not pkg:
        raise exceptions.ValidationError({"boost_type": "Invalid boost package."})

    if boost_type == MarketplaceBoost.BoostType.PRODUCT_7D:
        if product is None:
            raise exceptions.ValidationError({"product": "Select a published product or service to boost."})
        if product.organization_id != organization.id:
            raise exceptions.PermissionDenied("Selected product does not belong to your workspace.")
        if product.status != Product.Status.PUBLISHED:
            raise exceptions.ValidationError({"product": "Only published products or services can be boosted."})
    else:
        product = None

    now = timezone.now()
    duration_days = int(pkg["duration_days"])

    if use_plan_credit:
        if not pkg["eligible_for_plan_credit"]:
            raise exceptions.ValidationError(
                {"use_plan_credit": "Monthly plan boost credits apply to 7-Day Area Spotlight or 7-Day Listing Boost."}
            )
        # Serialize concurrent credit redemptions per organization inside this transaction
        sub = get_or_create_subscription(organization)
        Subscription.objects.select_for_update().filter(id=sub.id).first()
        used, limit = get_monthly_boost_credit_usage(organization)
        if used >= limit:
            raise exceptions.PermissionDenied(
                f"No free monthly boost credits remaining ({used}/{limit} used this month). "
                "Purchase a boost or upgrade to Growth/Professional for included monthly credits."
            )
        boost = MarketplaceBoost.objects.create(
            organization=organization,
            boost_type=boost_type,
            product=product,
            status=MarketplaceBoost.Status.ACTIVE,
            amount=Decimal("0.00"),
            currency=pkg["currency"],
            duration_days=duration_days,
            starts_at=now,
            ends_at=now + timedelta(days=duration_days),
            used_plan_credit=True,
            initiated_by=actor,
        )
        AuditLog.objects.create(
            organization=organization,
            actor=actor,
            action="boost_activated_via_plan_credit",
            target_type="MarketplaceBoost",
            target_id=str(boost.id),
            reason=f"Activated {pkg['name']} using included monthly plan credit.",
            metadata={"boost_type": boost_type, "duration_days": duration_days},
        )
        return boost, None

    amount: Decimal = pkg["amount"]
    currency: str = pkg["currency"]
    reference = f"BST-{now.strftime('%Y%m%d')}-{secrets.token_hex(6).upper()}"
    resolved_callback = _resolve_safe_callback_url(callback_url, _default_billing_callback_url())
    customer_email = (getattr(actor, "email", "") or organization.email or "").strip()
    paystack_init = initialize_paystack_transaction(
        email=customer_email,
        amount=amount,
        reference=reference,
        currency=currency,
        callback_url=resolved_callback,
        metadata={
            "purpose": "boost",
            "organization_id": str(organization.id),
            "boost_type": boost_type,
            "product_id": str(product.id) if product else "",
        },
    )

    tx = PaymentTransaction.objects.create(
        organization=organization,
        purpose=PaymentTransaction.Purpose.BOOST,
        reference=reference,
        provider="paystack",
        amount=amount,
        currency=currency,
        status=PaymentTransaction.Status.PENDING,
        authorization_url=(paystack_init.get("authorization_url", "") if paystack_init else ""),
        access_code=(paystack_init.get("access_code", "") if paystack_init else ""),
        initiated_by=actor,
    )
    boost = MarketplaceBoost.objects.create(
        organization=organization,
        boost_type=boost_type,
        product=product,
        status=MarketplaceBoost.Status.PENDING_PAYMENT,
        amount=amount,
        currency=currency,
        duration_days=duration_days,
        used_plan_credit=False,
        payment_transaction=tx,
        initiated_by=actor,
    )
    return boost, tx


@transaction.atomic
def _activate_boost_for_transaction(tx: PaymentTransaction) -> MarketplaceBoost | None:
    boost = (
        MarketplaceBoost.objects.select_for_update()
        .filter(payment_transaction=tx)
        .first()
    )
    if not boost:
        return None
    if boost.status == MarketplaceBoost.Status.ACTIVE:
        return boost
    now = timezone.now()
    # If org already has an active boost of the same type/product, extend seamlessly from its ends_at
    existing_active = (
        MarketplaceBoost.objects.filter(
            organization=tx.organization,
            boost_type=boost.boost_type,
            product=boost.product,
            status=MarketplaceBoost.Status.ACTIVE,
            ends_at__gt=now,
        )
        .order_by("-ends_at")
        .first()
    )
    start_anchor = existing_active.ends_at if existing_active and existing_active.ends_at else now
    boost.status = MarketplaceBoost.Status.ACTIVE
    boost.starts_at = now
    boost.ends_at = start_anchor + timedelta(days=boost.duration_days)
    boost.save(update_fields=["status", "starts_at", "ends_at", "updated_at"])
    AuditLog.objects.create(
        organization=tx.organization,
        actor=None,
        action="boost_activated",
        target_type="MarketplaceBoost",
        target_id=str(boost.id),
        reason=f"Paystack verified {boost.get_boost_type_display()} ({tx.currency} {tx.amount}).",
        metadata={"reference": tx.reference, "ends_at": boost.ends_at.isoformat()},
    )
    return boost


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
    Idempotently verify and apply a Paystack `charge.success` event for:
    - Escrow contracts (`ESC-...`)
    - Marketplace Spotlight Boosts (`BST-...`)
    - SaaS Subscriptions (`ART-...`, monthly or annual)
    Never trusts frontend payment callbacks; validates kobo amount and currency against server records.
    """
    event = payload.get("event")
    data = payload.get("data") or {}
    reference = data.get("reference")

    if event != "charge.success" or not reference:
        return {"processed": False, "detail": "Ignored non-charge.success event."}

    # 1. Customer Escrow funding references (ESC-...)
    if str(reference).startswith("ESC-"):
        from escrow.models import EscrowTransaction
        from escrow.services import fund_escrow_transaction

        escrow = (
            EscrowTransaction.objects.select_for_update()
            .filter(reference=reference)
            .first()
        )
        if not escrow:
            raise exceptions.NotFound("Escrow transaction reference not found.")
        if escrow.status == EscrowTransaction.Status.FUNDED_HELD:
            return {"processed": True, "detail": "Escrow already funded (idempotent)."}

        paid_minor = data.get("amount")
        paid_currency = (data.get("currency") or "").upper()
        payable = (
            escrow.total_payable_amount
            if escrow.total_payable_amount and escrow.total_payable_amount > Decimal("0.00")
            else escrow.total_amount
        )
        expected_minor = int((payable * Decimal("100")).quantize(Decimal("1")))
        if paid_minor != expected_minor or paid_currency != escrow.currency.upper():
            raise exceptions.ValidationError("Webhook escrow payment amount or currency mismatch.")

        fund_escrow_transaction(escrow=escrow, actor=None, via_webhook=True, provider_payload=payload)
        return {"processed": True, "detail": f"Funded escrow {escrow.reference}."}

    # 2. Subscription (ART-...) and Boost (BST-...) transactions
    tx = (
        PaymentTransaction.objects.select_for_update()
        .filter(reference=reference)
        .first()
    )
    if not tx:
        raise exceptions.NotFound("Payment transaction reference not found.")

    if tx.status == PaymentTransaction.Status.SUCCEEDED:
        return {"processed": True, "detail": "Already verified (idempotent)."}
    if tx.status == PaymentTransaction.Status.REFUNDED:
        raise exceptions.ValidationError("Payment transaction has already been refunded.")

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

    if tx.purpose == PaymentTransaction.Purpose.BOOST or str(reference).startswith("BST-"):
        boost = _activate_boost_for_transaction(tx)
        label = boost.get_boost_type_display() if boost else "Boost"
        return {"processed": True, "detail": f"Activated {label} for {tx.organization.name}."}

    sub = tx.subscription or get_or_create_subscription(tx.organization)
    if tx.plan:
        sub.plan = tx.plan
    sub.status = Subscription.Status.ACTIVE
    sub.billing_cycle = tx.billing_cycle
    sub.provider = Subscription.Provider.PAYSTACK
    sub.provider_reference = reference
    sub.current_period_start = now
    period_days = 365 if tx.billing_cycle == Subscription.BillingCycle.ANNUAL else 30
    sub.current_period_end = now + timedelta(days=period_days)
    sub.save()

    AuditLog.objects.create(
        organization=tx.organization,
        actor=None,
        action="payment_verified",
        target_type="PaymentTransaction",
        target_id=str(tx.id),
        reason=f"Paystack verified {tx.billing_cycle} payment for plan '{sub.plan.code}'.",
        metadata={
            "reference": reference,
            "amount": str(tx.amount),
            "currency": tx.currency,
            "billing_cycle": tx.billing_cycle,
        },
    )
    return {"processed": True, "detail": f"Upgraded {tx.organization.name} to {sub.plan.name} ({tx.billing_cycle})."}


@transaction.atomic
def _deliver_escrow_pin_to_customer_once(escrow_reference: str, actor) -> tuple[str | None, str]:
    """
    Ensure the authenticated customer receives their private 6-digit Completion PIN once upon returning
    from Paystack Hosted Checkout — even if Paystack's webhook funded the escrow a moment earlier.
    Returns (escrow_id_str, raw_pin) when eligible, or (escrow_id_str, "") if already delivered or non-customer.
    """
    from escrow.models import EscrowTransaction
    from escrow.services import generate_completion_pin, hash_completion_pin

    locked = (
        EscrowTransaction.objects.select_for_update()
        .filter(reference=escrow_reference)
        .first()
    )
    if not locked:
        return None, ""
    if actor is None or locked.customer_user_id != actor.id:
        return str(locked.id), ""
    if locked.status != EscrowTransaction.Status.FUNDED_HELD:
        return str(locked.id), ""

    payload = dict(locked.provider_payload or {})
    if payload.get("_pin_delivered"):
        return str(locked.id), ""

    raw_pin = generate_completion_pin()
    locked.completion_pin_hash = hash_completion_pin(raw_pin)
    payload["_pin_delivered"] = True
    locked.provider_payload = payload
    locked.save(update_fields=["completion_pin_hash", "provider_payload", "updated_at"])
    return str(locked.id), raw_pin


def _assert_actor_can_verify_reference(reference: str, actor) -> None:
    """Enforce tenant / customer ownership before verifying or disclosing a Paystack payment reference."""
    if actor is None or getattr(actor, "is_platform_admin", False):
        return

    cleaned = (reference or "").strip()
    if cleaned.startswith("ESC-"):
        from escrow.models import EscrowTransaction

        escrow = EscrowTransaction.objects.filter(reference=cleaned).first()
        if not escrow:
            raise exceptions.NotFound("Escrow transaction reference not found.")
        is_org_member = Membership.objects.filter(
            user=actor,
            organization_id=escrow.organization_id,
            status=Membership.Status.ACTIVE,
        ).exists()
        if escrow.customer_user_id != actor.id and not is_org_member:
            raise exceptions.PermissionDenied("You do not have permission to verify this escrow payment.")
        return

    tx = PaymentTransaction.objects.filter(reference=cleaned).first()
    if not tx:
        raise exceptions.NotFound("Payment transaction reference not found.")
    is_org_member = Membership.objects.filter(
        user=actor,
        organization_id=tx.organization_id,
        status=Membership.Status.ACTIVE,
    ).exists()
    if not is_org_member:
        raise exceptions.PermissionDenied("You do not have permission to verify this payment reference.")


def verify_and_apply_paystack_reference(reference: str, actor=None) -> dict:
    """
    Actively verify a Paystack payment reference server-side (`GET /transaction/verify/{reference}`)
    and apply it idempotently when the user returns from Paystack Hosted Checkout.
    """
    cleaned = (reference or "").strip()
    if not cleaned:
        raise exceptions.ValidationError({"reference": "Payment reference is required."})

    _assert_actor_can_verify_reference(cleaned, actor)

    data = verify_paystack_transaction(cleaned)
    if not data:
        raise exceptions.ValidationError(
            "Could not verify payment with Paystack right now. If you already paid, confirmation will apply automatically via webhook."
        )
    if (data.get("status") or "").lower() != "success":
        raise exceptions.ValidationError(
            f"Paystack transaction status is '{data.get('status', 'pending')}', not yet completed."
        )
    result = process_paystack_webhook_event({"event": "charge.success", "data": data})
    if cleaned.startswith("ESC-"):
        escrow_id, raw_pin = _deliver_escrow_pin_to_customer_once(cleaned, actor)
        if escrow_id:
            result["escrow_id"] = escrow_id
        if raw_pin:
            result["completion_pin"] = raw_pin
    return result


def get_platform_revenue_summary() -> dict:
    """Compute real-time multi-stream NGN platform revenue KPIs for Platform Admin."""
    from escrow.models import EscrowTransaction

    now = timezone.now()
    since_30d = now - timedelta(days=30)

    def _dec(val) -> Decimal:
        if val is None:
            return Decimal("0.00")
        return Decimal(str(val)).quantize(Decimal("0.01"))

    sub_qs = PaymentTransaction.objects.filter(
        purpose=PaymentTransaction.Purpose.SUBSCRIPTION,
        status=PaymentTransaction.Status.SUCCEEDED,
    )
    boost_qs = PaymentTransaction.objects.filter(
        purpose=PaymentTransaction.Purpose.BOOST,
        status=PaymentTransaction.Status.SUCCEEDED,
    )

    sub_rev_total = _dec(sub_qs.aggregate(total=Sum("amount"))["total"])
    sub_rev_30d = _dec(sub_qs.filter(verified_at__gte=since_30d).aggregate(total=Sum("amount"))["total"])
    boost_rev_total = _dec(boost_qs.aggregate(total=Sum("amount"))["total"])
    boost_rev_30d = _dec(boost_qs.filter(verified_at__gte=since_30d).aggregate(total=Sum("amount"))["total"])

    # Active paid subscriptions & estimated MRR
    active_subs = list(
        Subscription.objects.select_related("plan").filter(
            status=Subscription.Status.ACTIVE,
            organization__is_active=True,
        )
    )
    estimated_mrr = Decimal("0.00")
    active_paid_subscriptions = 0
    plan_stats: dict[str, dict] = {}
    for plan in Plan.objects.filter(is_active=True).order_by("display_order", "monthly_price"):
        plan_stats[plan.code] = {
            "plan_code": plan.code,
            "plan_name": plan.name,
            "monthly_price": plan.monthly_price,
            "active_count": 0,
            "mrr": Decimal("0.00"),
        }

    for sub in active_subs:
        p = sub.plan
        if p.code not in plan_stats:
            plan_stats[p.code] = {
                "plan_code": p.code,
                "plan_name": p.name,
                "monthly_price": p.monthly_price,
                "active_count": 0,
                "mrr": Decimal("0.00"),
            }
        plan_stats[p.code]["active_count"] += 1
        if p.monthly_price > Decimal("0.00"):
            active_paid_subscriptions += 1
            monthly_equiv = (
                (p.annual_price / Decimal("12")).quantize(Decimal("0.01"))
                if sub.billing_cycle == Subscription.BillingCycle.ANNUAL and p.annual_price > Decimal("0.00")
                else p.monthly_price
            )
            estimated_mrr += monthly_equiv
            plan_stats[p.code]["mrr"] += monthly_equiv

    estimated_mrr = _dec(estimated_mrr)

    # Escrow GMV, earned platform fees (from released escrows), and currently held balance
    funded_statuses = [
        EscrowTransaction.Status.FUNDED_HELD,
        EscrowTransaction.Status.WORK_SUBMITTED,
        EscrowTransaction.Status.RELEASED,
        EscrowTransaction.Status.DISPUTED,
    ]
    held_statuses = [
        EscrowTransaction.Status.FUNDED_HELD,
        EscrowTransaction.Status.WORK_SUBMITTED,
        EscrowTransaction.Status.DISPUTED,
    ]
    escrow_gmv_total = _dec(
        EscrowTransaction.objects.filter(status__in=funded_statuses).aggregate(total=Sum("total_amount"))["total"]
    )
    escrow_held_balance = _dec(
        EscrowTransaction.objects.filter(status__in=held_statuses).aggregate(total=Sum("held_in_escrow_amount"))["total"]
    )
    released_escrows = EscrowTransaction.objects.filter(status=EscrowTransaction.Status.RELEASED)
    escrow_fee_total = _dec(released_escrows.aggregate(total=Sum("platform_fee_amount"))["total"])
    escrow_fee_30d = _dec(
        released_escrows.filter(released_at__gte=since_30d).aggregate(total=Sum("platform_fee_amount"))["total"]
    )

    active_boosts_count = MarketplaceBoost.objects.filter(
        status=MarketplaceBoost.Status.ACTIVE,
        ends_at__gt=now,
    ).count()

    total_platform_revenue = _dec(sub_rev_total + boost_rev_total + escrow_fee_total)
    revenue_30d = _dec(sub_rev_30d + boost_rev_30d + escrow_fee_30d)

    recent_txs = list(
        PaymentTransaction.objects.select_related("organization", "plan")
        .prefetch_related("boosts")
        .filter(status=PaymentTransaction.Status.SUCCEEDED, amount__gt=Decimal("0.00"))
        .order_by("-verified_at", "-created_at")[:15]
    )

    def _tx_label(tx: PaymentTransaction) -> str:
        if tx.plan:
            return tx.plan.name
        first_boost = next(iter(tx.boosts.all()), None)
        return first_boost.get_boost_type_display() if first_boost else "Marketplace Boost"

    return {
        "currency": "NGN",
        "total_platform_revenue": total_platform_revenue,
        "revenue_30d": revenue_30d,
        "estimated_mrr": estimated_mrr,
        "subscription_revenue_total": sub_rev_total,
        "subscription_revenue_30d": sub_rev_30d,
        "active_paid_subscriptions": active_paid_subscriptions,
        "boost_revenue_total": boost_rev_total,
        "boost_revenue_30d": boost_rev_30d,
        "active_boosts_count": active_boosts_count,
        "escrow_gmv_total": escrow_gmv_total,
        "escrow_held_balance": escrow_held_balance,
        "escrow_fee_revenue_total": escrow_fee_total,
        "escrow_fee_revenue_30d": escrow_fee_30d,
        "plan_breakdown": list(plan_stats.values()),
        "recent_transactions": [
            {
                "id": tx.id,
                "reference": tx.reference,
                "purpose": tx.purpose,
                "organization_name": tx.organization.name,
                "label": _tx_label(tx),
                "amount": tx.amount,
                "currency": tx.currency,
                "verified_at": tx.verified_at or tx.created_at,
            }
            for tx in recent_txs
        ],
    }
