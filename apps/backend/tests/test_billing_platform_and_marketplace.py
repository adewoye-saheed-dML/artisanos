import hashlib
import hmac
import json

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from billing.models import AuditLog, Plan
from billing.seed import seed_default_plans
from catalog.models import Product, Storefront
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_subscription_usage_limit_and_paystack_webhook_upgrade(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_artisanos_secret"
    plans = seed_default_plans()
    starter = plans["starter"]
    starter.max_customers = 1
    starter.save(update_fields=["max_customers"])

    owner = User.objects.create_user(email="bill@atelier.ng", password="StrongPassword123!", full_name="Owner")
    org, _ = create_organization_with_owner(user=owner, name="Billing Atelier")

    client = APIClient()
    client.force_authenticate(user=owner)
    hdr = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    # 1st customer succeeds, 2nd hits Starter plan limit (403)
    c1 = client.post(
        reverse("customer-list"),
        {"full_name": "Customer One", "phone": "+2348011110001"},
        format="json",
        **hdr,
    )
    assert c1.status_code == 201

    c2 = client.post(
        reverse("customer-list"),
        {"full_name": "Customer Two", "phone": "+2348011110002"},
        format="json",
        **hdr,
    )
    assert c2.status_code == 403

    # Initiate checkout for Growth plan (NGN 15,000.00 -> 1,500,000 kobo)
    checkout_res = client.post(
        reverse("subscription-checkout"),
        {"plan_code": "growth"},
        format="json",
        **hdr,
    )
    assert checkout_res.status_code == 201
    reference = checkout_res.data["reference"]
    assert checkout_res.data["status"] == "pending"

    webhook_url = reverse("paystack-webhook")
    pub_client = APIClient()

    # Invalid signature must be rejected (401)
    bad_sig = pub_client.post(
        webhook_url,
        data=json.dumps({"event": "charge.success", "data": {"reference": reference}}),
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE="deadbeef",
    )
    assert bad_sig.status_code == 401

    # Valid HMAC-SHA512 signed webhook upgrades subscription to Growth
    payload = {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "amount": 1500000,
            "currency": "NGN",
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()

    ok_hook = pub_client.post(
        webhook_url,
        data=raw_body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert ok_hook.status_code == 200
    assert ok_hook.data["processed"] is True

    # Idempotent replay also succeeds without error
    replay_hook = pub_client.post(
        webhook_url,
        data=raw_body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert replay_hook.status_code == 200

    # Overview reflects Growth plan and 2nd customer now succeeds
    ov = client.get(reverse("subscription-overview"), **hdr)
    assert ov.status_code == 200
    assert ov.data["subscription"]["plan"]["code"] == "growth"

    c2_after = client.post(
        reverse("customer-list"),
        {"full_name": "Customer Two", "phone": "+2348011110002"},
        format="json",
        **hdr,
    )
    assert c2_after.status_code == 201


@pytest.mark.django_db
def test_platform_admin_suspend_reactivate_audit_and_marketplace_discovery():
    seed_default_plans()
    admin_user = User.objects.create_user(
        email="admin@artisanos.io",
        password="StrongPassword123!",
        full_name="Platform Admin",
        is_platform_admin=True,
    )
    regular_user = User.objects.create_user(
        email="artisan@shop.ng",
        password="StrongPassword123!",
        full_name="Artisan Owner",
    )
    org, _ = create_organization_with_owner(user=regular_user, name="Ikoyi Silk House", city="Lagos")
    Storefront.objects.create(organization=org, headline="Bespoke Silk", is_published=True)
    Product.objects.create(
        organization=org,
        name="Silk Kaftan",
        slug="silk-kaftan",
        price="85000.00",
        status=Product.Status.PUBLISHED,
        created_by=regular_user,
    )

    # Regular user blocked from platform admin
    reg_client = APIClient()
    reg_client.force_authenticate(user=regular_user)
    assert reg_client.get(reverse("platform-admin-overview")).status_code == 403

    # Marketplace discovers active published storefront and product
    pub_client = APIClient()
    sf_list = pub_client.get(reverse("marketplace-storefronts"))
    assert sf_list.status_code == 200
    assert any(s["slug"] == org.slug for s in sf_list.data)
    prod_list = pub_client.get(reverse("marketplace-products"))
    assert prod_list.status_code == 200
    assert any(p["name"] == "Silk Kaftan" for p in prod_list.data)

    # Platform admin suspends organization -> tenant API & marketplace immediately exclude it
    adm_client = APIClient()
    adm_client.force_authenticate(user=admin_user)
    susp_res = adm_client.post(
        reverse("platform-admin-suspend", args=[org.id]),
        {"reason": "Compliance verification pending"},
        format="json",
    )
    assert susp_res.status_code == 200
    assert AuditLog.objects.filter(organization=org, action="organization_suspended").exists()

    assert reg_client.get(reverse("customer-list"), HTTP_X_ORGANIZATION_ID=str(org.id)).status_code == 403
    assert not any(s["slug"] == org.slug for s in pub_client.get(reverse("marketplace-storefronts")).data)

    # Platform admin reactivates organization
    react_res = adm_client.post(
        reverse("platform-admin-reactivate", args=[org.id]),
        {"reason": "Compliance verified"},
        format="json",
    )
    assert react_res.status_code == 200
    assert reg_client.get(reverse("customer-list"), HTTP_X_ORGANIZATION_ID=str(org.id)).status_code == 200
