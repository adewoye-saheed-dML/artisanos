import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Membership


@pytest.mark.django_db
def test_register_with_workspace_sets_httponly_cookies_and_returns_org():
    client = APIClient()
    res = client.post(
        reverse("auth-register"),
        {
            "email": "ada@tailorstudio.ng",
            "password": "StrongPassword123!",
            "full_name": "Ada Lovelace",
            "phone": "+2348012345678",
            "organization_name": "Ada Bespoke Tailors",
            "organization_category": "tailor",
            "currency": "NGN",
            "preferred_unit": "cm",
        },
        format="json",
    )
    assert res.status_code == 201
    assert "access_token" in res.cookies
    assert res.cookies["access_token"]["httponly"] is True
    assert "refresh_token" in res.cookies
    assert res.cookies["refresh_token"]["httponly"] is True

    user_data = res.data["user"]
    assert user_data["email"] == "ada@tailorstudio.ng"
    assert len(user_data["memberships"]) == 1
    assert user_data["memberships"][0]["role"] == "owner"
    assert user_data["memberships"][0]["organization"]["name"] == "Ada Bespoke Tailors"


@pytest.mark.django_db
def test_cookie_auth_requires_csrf_on_mutations_and_supports_logout():
    client = APIClient(enforce_csrf_checks=True)
    csrf_res = client.get(reverse("auth-csrf"))
    assert csrf_res.status_code == 200
    csrf_token = csrf_res.cookies["csrftoken"].value

    reg_res = client.post(
        reverse("auth-register"),
        {
            "email": "kemi@atelier.com",
            "password": "StrongPassword123!",
            "full_name": "Kemi Tailor",
            "organization_name": "Kemi Atelier",
        },
        format="json",
    )
    assert reg_res.status_code == 201

    # Mutation without X-CSRFToken must be rejected by CookieJWTAuthentication
    no_csrf_res = client.post(
        reverse("organization-list"),
        {"name": "Second Studio", "category": "tailor"},
        format="json",
    )
    assert no_csrf_res.status_code == 403

    # Mutation with X-CSRFToken succeeds
    csrf_token = client.cookies["csrftoken"].value
    with_csrf_res = client.post(
        reverse("organization-list"),
        {"name": "Second Studio", "category": "tailor"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert with_csrf_res.status_code == 201
    assert with_csrf_res.data["name"] == "Second Studio"

    # Logout clears cookies
    logout_res = client.post(reverse("auth-logout"), {}, format="json", HTTP_X_CSRFTOKEN=csrf_token)
    assert logout_res.status_code == 200
    assert logout_res.cookies["access_token"].value == ""


@pytest.mark.django_db
def test_artisan_role_cannot_update_organization_settings():
    owner = User.objects.create_user(email="owner@studio.com", password="StrongPassword123!", full_name="Owner")
    artisan = User.objects.create_user(email="artisan@studio.com", password="StrongPassword123!", full_name="Artisan")

    owner_client = APIClient()
    owner_client.force_authenticate(user=owner)
    org_res = owner_client.post(
        reverse("organization-list"),
        {"name": "Royal Stitches", "category": "tailor"},
        format="json",
    )
    org_id = org_res.data["id"]

    Membership.objects.create(
        user=artisan,
        organization_id=org_id,
        role=Membership.Role.ARTISAN,
        status=Membership.Status.ACTIVE,
    )

    artisan_client = APIClient()
    artisan_client.force_authenticate(user=artisan)
    patch_res = artisan_client.patch(
        reverse("organization-detail", args=[org_id]),
        {"name": "Hijacked Name"},
        format="json",
    )
    assert patch_res.status_code == 403
