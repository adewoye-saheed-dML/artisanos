import hashlib
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from billing.models import AuditLog
from notifications.models import Notification
from notifications.services import create_notification
from orders.models import Order
from organizations.models import Membership, Organization

from .models import EscrowEvent, EscrowTransaction

ESCROW_FEE_RATE = Decimal("0.03")  # Transparent 3% escrow protection fee
MAX_MATERIALS_ADVANCE_PCT = 30  # At least 70%–100% stays strictly protected in escrow until completion


def hash_completion_pin(pin: str) -> str:
    return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()


def generate_completion_pin() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def compute_escrow_breakdown(total_amount: Decimal, materials_advance_pct: int = 0) -> dict:
    if total_amount <= Decimal("0.00"):
        raise exceptions.ValidationError({"total_amount": "Escrow amount must be greater than zero."})
    if materials_advance_pct < 0 or materials_advance_pct > MAX_MATERIALS_ADVANCE_PCT:
        raise exceptions.ValidationError(
            {
                "materials_advance_pct": (
                    f"Upfront materials advance cannot exceed {MAX_MATERIALS_ADVANCE_PCT}%. "
                    "At least 70% must stay locked in escrow until work is completed."
                )
            }
        )
    advance = (total_amount * Decimal(materials_advance_pct) / Decimal("100")).quantize(Decimal("0.01"))
    held = (total_amount - advance).quantize(Decimal("0.01"))
    platform_fee = (total_amount * ESCROW_FEE_RATE).quantize(Decimal("0.01"))
    artisan_payout = (total_amount - platform_fee).quantize(Decimal("0.01"))
    return {
        "materials_advance_amount": advance,
        "held_in_escrow_amount": held,
        "platform_fee_amount": platform_fee,
        "artisan_payout_amount": artisan_payout,
    }


@transaction.atomic
def create_escrow_contract(
    *,
    customer_user,
    organization: Organization,
    job_title: str,
    total_amount: Decimal,
    job_description: str = "",
    materials_advance_pct: int = 0,
    customer_name: str = "",
    customer_phone: str = "",
    customer_email: str = "",
    order: Order | None = None,
    inquiry=None,
) -> EscrowTransaction:
    if not organization.is_active:
        raise exceptions.ValidationError("This artisan workspace is not active.")
    if not organization.is_verified:
        raise exceptions.PermissionDenied(
            "Escrow protection is only available for NIN/CAC verified artisans."
        )
    if order is not None and order.organization_id != organization.id:
        raise exceptions.ValidationError({"order": "Order does not belong to this artisan."})
    if inquiry is not None and inquiry.organization_id != organization.id:
        raise exceptions.ValidationError({"inquiry": "Inquiry does not belong to this artisan."})

    # Prevent artisan from creating fake self-escrow with their own workspace
    if Membership.objects.filter(
        user=customer_user,
        organization=organization,
        status=Membership.Status.ACTIVE,
    ).exists():
        raise exceptions.PermissionDenied("You cannot open a customer escrow contract with your own workspace.")

    breakdown = compute_escrow_breakdown(total_amount, materials_advance_pct)
    reference = f"ESC-{timezone.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

    escrow = EscrowTransaction.objects.create(
        reference=reference,
        organization=organization,
        customer_user=customer_user,
        order=order,
        inquiry=inquiry,
        customer_name=(customer_name or customer_user.full_name).strip()[:150],
        customer_phone=(customer_phone or customer_user.phone or "N/A").strip()[:32],
        customer_email=(customer_email or customer_user.email).strip(),
        job_title=job_title.strip()[:180],
        job_description=job_description.strip(),
        total_amount=total_amount,
        materials_advance_pct=materials_advance_pct,
        materials_advance_amount=breakdown["materials_advance_amount"],
        held_in_escrow_amount=breakdown["held_in_escrow_amount"],
        platform_fee_amount=breakdown["platform_fee_amount"],
        artisan_payout_amount=breakdown["artisan_payout_amount"],
        currency=organization.currency,
        status=EscrowTransaction.Status.AWAITING_FUNDING,
        payment_provider="paystack" if getattr(settings, "PAYSTACK_SECRET_KEY", "") else "escrow_sandbox",
    )

    EscrowEvent.objects.create(
        escrow=escrow,
        actor=customer_user,
        event_type="created",
        from_status="",
        to_status=EscrowTransaction.Status.AWAITING_FUNDING,
        notes=f"Escrow contract opened for {escrow.currency} {escrow.total_amount} (held in escrow: {escrow.held_in_escrow_amount}).",
    )
    return escrow


@transaction.atomic
def fund_escrow_transaction(
    *,
    escrow: EscrowTransaction,
    actor=None,
    via_webhook: bool = False,
    provider_payload: dict | None = None,
) -> tuple[EscrowTransaction, str]:
    """
    Lock customer funds in ArtisanOS Escrow and generate a one-time 6-digit Completion Release PIN
    delivered exclusively to the customer.
    When PAYSTACK_SECRET_KEY is configured, funding MUST come through a verified Paystack webhook.
    """
    locked = EscrowTransaction.objects.select_for_update().select_related("organization").get(id=escrow.id)

    if not via_webhook:
        if actor is None or locked.customer_user_id != actor.id:
            raise exceptions.PermissionDenied("Only the customer who opened this escrow can fund it.")
        if getattr(settings, "PAYSTACK_SECRET_KEY", ""):
            raise exceptions.ValidationError(
                "Live Paystack mode is enabled: escrow funding is confirmed strictly via verified Paystack webhook."
            )

    if locked.status == EscrowTransaction.Status.FUNDED_HELD:
        return locked, ""
    if locked.status != EscrowTransaction.Status.AWAITING_FUNDING:
        raise exceptions.ValidationError(f"Cannot fund escrow while in '{locked.status}' state.")

    raw_pin = generate_completion_pin()
    now = timezone.now()
    locked.status = EscrowTransaction.Status.FUNDED_HELD
    locked.completion_pin_hash = hash_completion_pin(raw_pin)
    locked.funded_at = now
    locked.payment_provider = "paystack" if via_webhook else "escrow_sandbox"
    if provider_payload:
        locked.provider_payload = provider_payload
    locked.save(
        update_fields=[
            "status",
            "completion_pin_hash",
            "funded_at",
            "payment_provider",
            "provider_payload",
            "updated_at",
        ]
    )

    EscrowEvent.objects.create(
        escrow=locked,
        actor=actor,
        event_type="funded",
        from_status=EscrowTransaction.Status.AWAITING_FUNDING,
        to_status=EscrowTransaction.Status.FUNDED_HELD,
        notes=f"Customer funded {locked.currency} {locked.total_amount}. Funds locked safely in escrow.",
        metadata={"via_webhook": via_webhook},
    )

    create_notification(
        organization=locked.organization,
        event_type=Notification.EventType.SYSTEM,
        title=f"Escrow Funded ({locked.reference}) — Safe to Start Work!",
        message=(
            f"{locked.customer_name} has funded {locked.currency} {locked.total_amount} into ArtisanOS Escrow "
            f"for '{locked.job_title}'. Complete the job and mark it finished to receive release."
        ),
        link_path="/escrow",
    )
    return locked, raw_pin


@transaction.atomic
def submit_escrow_work(
    *,
    escrow: EscrowTransaction,
    actor,
    completion_notes: str = "",
) -> EscrowTransaction:
    """Artisan marks work completed and requests customer inspection & escrow release."""
    locked = EscrowTransaction.objects.select_for_update().select_related("organization").get(id=escrow.id)
    is_member = Membership.objects.filter(
        user=actor,
        organization=locked.organization,
        status=Membership.Status.ACTIVE,
    ).exists()
    if not is_member:
        raise exceptions.PermissionDenied("Only members of the assigned artisan workspace can submit completed work.")

    if locked.status != EscrowTransaction.Status.FUNDED_HELD:
        raise exceptions.ValidationError(
            f"Work can only be submitted when funds are held in escrow (current status: '{locked.status}')."
        )

    now = timezone.now()
    locked.status = EscrowTransaction.Status.WORK_SUBMITTED
    locked.artisan_completion_notes = completion_notes.strip()
    locked.work_submitted_at = now
    locked.save(update_fields=["status", "artisan_completion_notes", "work_submitted_at", "updated_at"])

    EscrowEvent.objects.create(
        escrow=locked,
        actor=actor,
        event_type="work_submitted",
        from_status=EscrowTransaction.Status.FUNDED_HELD,
        to_status=EscrowTransaction.Status.WORK_SUBMITTED,
        notes=completion_notes.strip() or "Artisan marked work completed and requested customer inspection.",
    )
    return locked


@transaction.atomic
def release_escrow_to_artisan(
    *,
    escrow: EscrowTransaction,
    actor,
    completion_pin: str = "",
    notes: str = "",
) -> EscrowTransaction:
    """
    Customer inspects completed work and explicitly releases full escrow funds to the artisan.
    Artisans can NEVER release escrow funds to themselves.
    """
    locked = EscrowTransaction.objects.select_for_update().select_related("organization", "order").get(id=escrow.id)

    if locked.customer_user_id != actor.id:
        raise exceptions.PermissionDenied(
            "Only the customer who funded this escrow can confirm completion and release payment."
        )
    if locked.status not in {
        EscrowTransaction.Status.FUNDED_HELD,
        EscrowTransaction.Status.WORK_SUBMITTED,
    }:
        raise exceptions.ValidationError(f"Escrow cannot be released from '{locked.status}' state.")

    if locked.completion_pin_hash:
        if not completion_pin or hash_completion_pin(completion_pin) != locked.completion_pin_hash:
            raise exceptions.ValidationError(
                {"completion_pin": "Invalid 6-digit escrow completion PIN. Check the PIN issued when you funded."}
            )

    prev = locked.status
    now = timezone.now()
    locked.status = EscrowTransaction.Status.RELEASED
    locked.released_at = now
    locked.save(update_fields=["status", "released_at", "updated_at"])

    if locked.order:
        locked.order.deposit_amount = locked.order.agreed_amount or locked.order.quoted_amount or locked.total_amount
        locked.order.payment_status = Order.PaymentStatus.PAID
        locked.order.save(update_fields=["deposit_amount", "payment_status", "updated_at"])

    EscrowEvent.objects.create(
        escrow=locked,
        actor=actor,
        event_type="released",
        from_status=prev,
        to_status=EscrowTransaction.Status.RELEASED,
        notes=notes.strip() or f"Customer confirmed work completed. {locked.currency} {locked.artisan_payout_amount} released to artisan.",
    )
    AuditLog.objects.create(
        organization=locked.organization,
        actor=actor,
        action="escrow_released",
        target_type="EscrowTransaction",
        target_id=str(locked.id),
        reason=notes.strip() or "Customer confirmed job completion.",
        metadata={
            "reference": locked.reference,
            "total_amount": str(locked.total_amount),
            "artisan_payout_amount": str(locked.artisan_payout_amount),
        },
    )
    create_notification(
        organization=locked.organization,
        event_type=Notification.EventType.SYSTEM,
        title=f"Escrow Released ({locked.reference}) — Payment Credited!",
        message=(
            f"{locked.customer_name} confirmed '{locked.job_title}' is complete. "
            f"Net payout of {locked.currency} {locked.artisan_payout_amount} has been released."
        ),
        link_path="/escrow",
    )
    return locked


@transaction.atomic
def dispute_escrow_transaction(
    *,
    escrow: EscrowTransaction,
    actor,
    reason: str,
) -> EscrowTransaction:
    """Customer freezes escrow funds and opens a platform-arbitrated dispute."""
    cleaned_reason = reason.strip()
    if len(cleaned_reason) < 8:
        raise exceptions.ValidationError(
            {"reason": "Describe the issue clearly (at least 8 characters) so platform admins can investigate."}
        )

    locked = EscrowTransaction.objects.select_for_update().select_related("organization").get(id=escrow.id)
    if locked.customer_user_id != actor.id:
        raise exceptions.PermissionDenied("Only the customer who funded this escrow can raise a dispute.")
    if locked.status not in {
        EscrowTransaction.Status.FUNDED_HELD,
        EscrowTransaction.Status.WORK_SUBMITTED,
    }:
        raise exceptions.ValidationError(f"Cannot dispute escrow in '{locked.status}' state.")

    prev = locked.status
    now = timezone.now()
    locked.status = EscrowTransaction.Status.DISPUTED
    locked.dispute_reason = cleaned_reason
    locked.disputed_at = now
    locked.save(update_fields=["status", "dispute_reason", "disputed_at", "updated_at"])

    EscrowEvent.objects.create(
        escrow=locked,
        actor=actor,
        event_type="disputed",
        from_status=prev,
        to_status=EscrowTransaction.Status.DISPUTED,
        notes=cleaned_reason,
    )
    create_notification(
        organization=locked.organization,
        event_type=Notification.EventType.SYSTEM,
        title=f"Escrow Dispute Opened ({locked.reference})",
        message=f"Customer raised a dispute on '{locked.job_title}'. Funds remain frozen pending platform review.",
        link_path="/escrow",
    )
    return locked


@transaction.atomic
def resolve_escrow_dispute(
    *,
    escrow: EscrowTransaction,
    admin_user,
    decision: str,
    reason: str,
) -> EscrowTransaction:
    """Platform Admin resolves a disputed escrow by refunding the customer or releasing to the artisan."""
    if not admin_user.is_platform_admin:
        raise exceptions.PermissionDenied("Only platform administrators can resolve escrow disputes.")
    cleaned_reason = reason.strip()
    if len(cleaned_reason) < 5:
        raise exceptions.ValidationError({"reason": "Provide a clear arbitration resolution reason."})
    if decision not in {"refund_customer", "release_to_artisan"}:
        raise exceptions.ValidationError({"decision": "Decision must be 'refund_customer' or 'release_to_artisan'."})

    locked = EscrowTransaction.objects.select_for_update().select_related("organization").get(id=escrow.id)
    if locked.status != EscrowTransaction.Status.DISPUTED:
        raise exceptions.ValidationError("Only disputed escrow transactions can be arbitrated.")

    now = timezone.now()
    new_status = (
        EscrowTransaction.Status.REFUNDED
        if decision == "refund_customer"
        else EscrowTransaction.Status.RELEASED
    )
    locked.status = new_status
    locked.resolution_notes = cleaned_reason
    locked.resolved_by = admin_user
    locked.resolved_at = now
    if new_status == EscrowTransaction.Status.RELEASED:
        locked.released_at = now
    locked.save(
        update_fields=[
            "status",
            "resolution_notes",
            "resolved_by",
            "resolved_at",
            "released_at",
            "updated_at",
        ]
    )

    EscrowEvent.objects.create(
        escrow=locked,
        actor=admin_user,
        event_type=f"admin_{decision}",
        from_status=EscrowTransaction.Status.DISPUTED,
        to_status=new_status,
        notes=cleaned_reason,
    )
    AuditLog.objects.create(
        organization=locked.organization,
        actor=admin_user,
        action=f"escrow_dispute_{decision}",
        target_type="EscrowTransaction",
        target_id=str(locked.id),
        reason=cleaned_reason,
        metadata={"reference": locked.reference, "decision": decision},
    )
    return locked


@transaction.atomic
def cancel_unfunded_escrow(*, escrow: EscrowTransaction, actor) -> EscrowTransaction:
    locked = EscrowTransaction.objects.select_for_update().get(id=escrow.id)
    if locked.customer_user_id != actor.id:
        raise exceptions.PermissionDenied("Only the customer can cancel an unfunded escrow contract.")
    if locked.status != EscrowTransaction.Status.AWAITING_FUNDING:
        raise exceptions.ValidationError("Only unfunded escrow contracts can be cancelled directly.")
    locked.status = EscrowTransaction.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    EscrowEvent.objects.create(
        escrow=locked,
        actor=actor,
        event_type="cancelled",
        from_status=EscrowTransaction.Status.AWAITING_FUNDING,
        to_status=EscrowTransaction.Status.CANCELLED,
        notes="Cancelled by customer before funding.",
    )
    return locked
