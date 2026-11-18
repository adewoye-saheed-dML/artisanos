import hashlib
import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import exceptions

from accounts.models import User

from .models import Membership, Organization, OrganizationInvitation


def hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_unique_org_slug(name: str) -> str:
    """Generate a unique URL-friendly slug for an organization."""
    base = slugify(name)[:140] or "workspace"
    candidate = base
    while Organization.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    return candidate


@transaction.atomic
def create_organization_with_owner(
    *,
    user,
    name: str,
    category: str = Organization.Category.TAILOR,
    email: str = "",
    phone: str = "",
    address: str = "",
    city: str = "",
    country: str = "",
    currency: str = "NGN",
    preferred_unit: str = Organization.UnitSystem.CM,
) -> tuple[Organization, Membership]:
    """Create an organization and assign the creating user as active owner."""
    org = Organization.objects.create(
        name=name.strip(),
        slug=generate_unique_org_slug(name),
        category=category,
        email=email.strip(),
        phone=phone.strip(),
        address=address.strip(),
        city=city.strip(),
        country=country.strip(),
        currency=currency.strip().upper(),
        preferred_unit=preferred_unit,
    )
    membership = Membership.objects.create(
        user=user,
        organization=org,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
    )
    return org, membership


def _get_actor_membership(user, organization: Organization) -> Membership:
    membership = Membership.objects.filter(
        user=user,
        organization=organization,
        status=Membership.Status.ACTIVE,
    ).first()
    if not membership:
        raise exceptions.PermissionDenied("You are not an active member of this organization.")
    return membership


@transaction.atomic
def create_invitation(
    *,
    organization: Organization,
    actor,
    email: str,
    role: str,
    expires_in_days: int = 7,
) -> tuple[OrganizationInvitation, str]:
    """Create a secure expiring team invitation enforcing owner/manager role rules."""
    actor_membership = _get_actor_membership(actor, organization)
    if actor_membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
        raise exceptions.PermissionDenied("Only organization owners or managers can invite team members.")

    from billing.services import enforce_plan_limit

    enforce_plan_limit(organization, "members")

    if role == Membership.Role.OWNER:
        raise exceptions.ValidationError({"role": "Owner role cannot be assigned directly via invitation."})
    if actor_membership.role == Membership.Role.MANAGER and role == Membership.Role.MANAGER:
        raise exceptions.PermissionDenied("Managers can only invite artisans or sales assistants.")

    normalized_email = email.strip().lower()
    if Membership.objects.filter(
        organization=organization,
        user__email__iexact=normalized_email,
        status=Membership.Status.ACTIVE,
    ).exists():
        raise exceptions.ValidationError({"email": "This user is already an active member of this workspace."})

    # Revoke any older pending invitations for the same email in this workspace
    OrganizationInvitation.objects.filter(
        organization=organization,
        email__iexact=normalized_email,
        status=OrganizationInvitation.Status.PENDING,
    ).update(status=OrganizationInvitation.Status.REVOKED)

    raw_token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email=normalized_email,
        role=role,
        token_hash=hash_invitation_token(raw_token),
        status=OrganizationInvitation.Status.PENDING,
        expires_at=timezone.now() + timedelta(days=expires_in_days),
        invited_by=actor,
    )
    return invitation, raw_token


@transaction.atomic
def update_member(
    *,
    organization: Organization,
    target_membership: Membership,
    actor,
    role: str | None = None,
    status: str | None = None,
) -> Membership:
    """Update a team member's role or status while protecting owner invariants."""
    actor_membership = _get_actor_membership(actor, organization)
    if target_membership.organization_id != organization.id:
        raise exceptions.PermissionDenied("Member does not belong to this organization.")
    if actor_membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
        raise exceptions.PermissionDenied("Only owners or managers can manage team roles.")

    if actor_membership.role == Membership.Role.MANAGER:
        if target_membership.role in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Managers cannot modify owners or other managers.")
        if role in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Managers cannot promote members to owner or manager.")

    new_role = role or target_membership.role
    new_status = status or target_membership.status

    # Ensure organization always retains at least one active owner
    if target_membership.role == Membership.Role.OWNER and (
        new_role != Membership.Role.OWNER or new_status != Membership.Status.ACTIVE
    ):
        other_active_owners = (
            Membership.objects.filter(
                organization=organization,
                role=Membership.Role.OWNER,
                status=Membership.Status.ACTIVE,
            )
            .exclude(id=target_membership.id)
            .count()
        )
        if other_active_owners == 0:
            raise exceptions.ValidationError(
                "Cannot demote or suspend the last active owner of an organization."
            )

    target_membership.role = new_role
    target_membership.status = new_status
    target_membership.save(update_fields=["role", "status", "updated_at"])
    return target_membership


def get_active_invitation_or_error(raw_token: str) -> OrganizationInvitation:
    token_hash = hash_invitation_token(raw_token)
    invitation = (
        OrganizationInvitation.objects.select_related("organization", "invited_by")
        .filter(token_hash=token_hash)
        .first()
    )
    if not invitation:
        raise exceptions.NotFound("Invitation not found.")
    if invitation.status == OrganizationInvitation.Status.REVOKED:
        raise exceptions.ValidationError("This invitation has been revoked.")
    if invitation.status == OrganizationInvitation.Status.ACCEPTED:
        raise exceptions.ValidationError("This invitation has already been accepted.")
    if invitation.status == OrganizationInvitation.Status.EXPIRED or invitation.expires_at <= timezone.now():
        if invitation.status == OrganizationInvitation.Status.PENDING:
            invitation.status = OrganizationInvitation.Status.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
        raise exceptions.ValidationError("This invitation has expired.")
    return invitation


@transaction.atomic
def accept_invitation(
    *,
    raw_token: str,
    authenticated_user=None,
    full_name: str = "",
    password: str = "",
    phone: str = "",
) -> tuple[User, Membership]:
    """
    Accept a pending team invitation.
    Works for an authenticated user matching the invited email, OR registers a
    new user account matching the invited email in a single atomic transaction.
    """
    invitation = get_active_invitation_or_error(raw_token)
    invited_email = invitation.email.strip().lower()

    if authenticated_user and authenticated_user.is_authenticated:
        if authenticated_user.email.strip().lower() != invited_email:
            raise exceptions.PermissionDenied(
                f"This invitation was issued for {invited_email}. Sign in with that account to accept."
            )
        user = authenticated_user
    else:
        existing = User.objects.filter(email__iexact=invited_email).first()
        if existing:
            if not password or not existing.check_password(password):
                raise exceptions.ValidationError(
                    {"password": "An account already exists for this email. Provide your password to accept."}
                )
            user = existing
        else:
            if len(full_name.strip()) < 2:
                raise exceptions.ValidationError({"full_name": "Full name is required to create your account."})
            if not password:
                raise exceptions.ValidationError({"password": "Password is required to create your account."})
            validate_password(password)
            user = User.objects.create_user(
                email=invited_email,
                password=password,
                full_name=full_name.strip(),
                phone=phone.strip(),
            )

    membership, created = Membership.objects.get_or_create(
        user=user,
        organization=invitation.organization,
        defaults={
            "role": invitation.role,
            "status": Membership.Status.ACTIVE,
        },
    )
    if not created:
        membership.role = invitation.role
        membership.status = Membership.Status.ACTIVE
        membership.save(update_fields=["role", "status", "updated_at"])

    invitation.status = OrganizationInvitation.Status.ACCEPTED
    invitation.accepted_by = user
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_by", "accepted_at", "updated_at"])
    return user, membership
