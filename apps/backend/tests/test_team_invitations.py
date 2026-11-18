import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Membership
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_owner_invites_artisan_and_new_user_accepts_and_joins_workspace():
    owner = User.objects.create_user(email="owner@bespoke.ng", password="StrongPassword123!", full_name="Ada Owner")
    org, owner_membership = create_organization_with_owner(user=owner, name="Ada Atelier")

    owner_client = APIClient()
    owner_client.force_authenticate(user=owner)

    # Owner creates invitation for a new tailor
    inv_res = owner_client.post(
        reverse("organization-invitations", args=[org.id]),
        {"email": "newtailor@bespoke.ng", "role": "artisan"},
        format="json",
    )
    assert inv_res.status_code == 201
    raw_token = inv_res.data["token"]
    assert inv_res.data["invite_path"] == f"/invite/{raw_token}"

    # Unauthenticated inspect returns org & role
    pub_client = APIClient()
    inspect_res = pub_client.get(reverse("public-invitation-detail", args=[raw_token]))
    assert inspect_res.status_code == 200
    assert inspect_res.data["organization_name"] == "Ada Atelier"
    assert inspect_res.data["role"] == "artisan"
    assert inspect_res.data["account_exists"] is False

    # New user accepts invitation and creates account in one step
    accept_res = pub_client.post(
        reverse("public-invitation-accept", args=[raw_token]),
        {"full_name": "Emeka Tailor", "password": "TailorPassword123!"},
        format="json",
    )
    assert accept_res.status_code == 200
    assert "access_token" in accept_res.cookies
    assert accept_res.data["role"] == "artisan"
    assert Membership.objects.filter(
        organization=org,
        user__email="newtailor@bespoke.ng",
        role=Membership.Role.ARTISAN,
        status=Membership.Status.ACTIVE,
    ).exists()

    # Reusing accepted invitation is blocked
    reuse_res = pub_client.get(reverse("public-invitation-detail", args=[raw_token]))
    assert reuse_res.status_code == 400

    # Owner cannot demote themselves when they are the last active owner
    demote_self = owner_client.patch(
        reverse("organization-update-member-detail", args=[org.id, owner_membership.id]),
        {"role": "manager"},
        format="json",
    )
    assert demote_self.status_code == 400


@pytest.mark.django_db
def test_manager_role_restrictions_and_invitation_revocation():
    owner = User.objects.create_user(email="owner2@bespoke.ng", password="StrongPassword123!", full_name="Owner")
    manager = User.objects.create_user(email="mgr@bespoke.ng", password="StrongPassword123!", full_name="Manager")
    org, owner_membership = create_organization_with_owner(user=owner, name="Savile Studio")
    Membership.objects.create(user=manager, organization=org, role=Membership.Role.MANAGER, status=Membership.Status.ACTIVE)

    mgr_client = APIClient()
    mgr_client.force_authenticate(user=manager)

    # Manager cannot invite another manager
    forbid_mgr_inv = mgr_client.post(
        reverse("organization-invitations", args=[org.id]),
        {"email": "other@bespoke.ng", "role": "manager"},
        format="json",
    )
    assert forbid_mgr_inv.status_code == 403

    # Manager cannot modify owner membership
    forbid_owner_edit = mgr_client.patch(
        reverse("organization-update-member-detail", args=[org.id, owner_membership.id]),
        {"status": "suspended"},
        format="json",
    )
    assert forbid_owner_edit.status_code == 403

    # Manager can invite sales assistant and revoke the invitation
    ok_inv = mgr_client.post(
        reverse("organization-invitations", args=[org.id]),
        {"email": "assistant@bespoke.ng", "role": "sales_assistant"},
        format="json",
    )
    assert ok_inv.status_code == 201
    invite_id = ok_inv.data["id"]
    token = ok_inv.data["token"]

    revoke_res = mgr_client.post(
        reverse("organization-revoke-invitation", args=[org.id, invite_id]),
        {},
        format="json",
    )
    assert revoke_res.status_code == 200
    assert revoke_res.data["status"] == "revoked"

    # Revoked token cannot be inspected or accepted
    pub_client = APIClient()
    assert pub_client.get(reverse("public-invitation-detail", args=[token])).status_code == 400
