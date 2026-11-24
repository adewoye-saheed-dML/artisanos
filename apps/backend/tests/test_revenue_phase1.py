import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from billing.models import MarketplaceBoost, PaymentTransaction, Plan
from billing.seed import seed_default_plans
from billing.services import get_platform_revenue_summary
from catalog.models import Product, Storefront
from escrow.services import compute_escrow_breakdown
from organizations.services import create_organization_with_owner


def _signed_post(client, settings, payload):
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), raw, hashlib.sha512).hexdigest()
    return client.post(
        reverse("paystack-webhook"),
        data=raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )


def _owner_client(email="owner@rev.ng", org_name="Revenue Workshop"):
    user = User.objects.create_user(email=email, password="StrongPassword123!", full_name="Owner")
    org, _ = create_organization_with_owner(user=user, name=org_name)
    client = APIClient()
    client.force_authenticate(user=user)
    return user, org, client, {"HTTP_X_ORGANIZATION_ID": str(org.id)}


@pytest.mark.django_db
def test_four_nigeria_calibrated_plans_and_split_escrow_fee_math():
    plans = seed_default_plans()
    assert set(plans) == {"starter", "solo_pro", "growth", "professional"}
    assert plans["solo_pro"].monthly_price == Decimal("3500.00")
    assert plans["solo_pro"].annual_price == Decimal("35000.00")
    assert plans["professional"].escrow_fee_rate_pct == Decimal("1.50")

    b = compute_escrow_breakdown(Decimal("50000.00"), 0, artisan_fee_rate_pct=Decimal("2.50"))
    assert b["artisan_fee_amount"] == Decimal("1250.00")
    assert b["customer_protection_fee_amount"] == Decimal("1000.00")
    assert b["total_payable_amount"] == Decimal("51000.00")
    assert b["artisan_payout_amount"] == Decimal("48750.00")
    assert b["platform_fee_amount"] == Decimal("2250.00")

    # Buyer protection fee is capped at NGN 5,000 for large jobs
    big = compute_escrow_breakdown(Decimal("1000000.00"), 0, artisan_fee_rate_pct=Decimal("2.00"))
    assert big["customer_protection_fee_amount"] == Decimal("5000.00")


@pytest.mark.django_db
def test_annual_plan_checkout_webhook_and_plan_limits_on_neighborhood_coverage(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_phase1_secret"
    seed_default_plans()
    _user, org, client, hdr = _owner_client()
    pub = APIClient()

    res = client.post(
        reverse("subscription-checkout"),
        {"plan_code": "solo_pro", "billing_cycle": "annual"},
        format="json",
        **hdr,
    )
    assert res.status_code == 201
    assert res.data["amount"] == "35000.00"
    assert res.data["billing_cycle"] == "annual"
    assert res.data["status"] == "pending"

    # Webhook with wrong amount is rejected; correct annual amount (3,500,000 kobo) activates plan
    bad = _signed_post(
        pub, settings, {"event": "charge.success", "data": {"reference": res.data["reference"], "amount": 350000, "currency": "NGN"}}
    )
    assert bad.status_code == 400
    # Rejected payment marks tx failed; open a fresh checkout
    res2 = client.post(
        reverse("subscription-checkout"),
        {"plan_code": "solo_pro", "billing_cycle": "annual"},
        format="json",
        **hdr,
    )
    ok = _signed_post(
        pub,
        settings,
        {"event": "charge.success", "data": {"reference": res2.data["reference"], "amount": 3500000, "currency": "NGN"}},
    )
    assert ok.status_code == 200
    overview = client.get(reverse("subscription-overview"), **hdr)
    assert overview.data["subscription"]["plan"]["code"] == "solo_pro"
    assert overview.data["subscription"]["billing_cycle"] == "annual"
    assert overview.data["usage"]["service_wards"]["limit"] == 5

    summary = get_platform_revenue_summary()
    assert summary["subscription_revenue_total"] == Decimal("35000.00")
    # Annual NGN 35,000 counts as NGN 2,916.67 / month MRR
    assert summary["estimated_mrr"] == Decimal("2916.67")
    assert summary["active_paid_subscriptions"] == 1


@pytest.mark.django_db
def test_boost_paid_via_webhook_plan_credit_and_marketplace_ranking(settings):
    settings.PAYSTACK_SECRET_KEY = "sk_test_boost_secret"
    plans = seed_default_plans()
    user_a, org_a, client_a, hdr_a = _owner_client("a@rev.ng", "Alpha Tailors")
    _user_b, org_b, _client_b, _hdr_b = _owner_client("b@rev.ng", "Beta Tailors")
    for org in (org_a, org_b):
        Storefront.objects.create(organization=org, headline="Tailor", is_published=True)
    product = Product.objects.create(
        organization=org_a,
        name="Agbada Set",
        slug="agbada-set",
        price="50000.00",
        status=Product.Status.PUBLISHED,
        created_by=user_a,
    )
    pub = APIClient()

    def names():
        return [r["organization_name"] for r in pub.get(reverse("marketplace-artisans")).data]

    # Without boosts, ordering is alphabetical (identical rank)
    # Packages listing exposes 3 Nigeria-calibrated boosts
    pk = client_a.get(reverse("boost-packages"), **hdr_a)
    assert pk.status_code == 200
    assert {p["code"] for p in pk.data["packages"]} == {"area_7d", "lga_30d", "product_7d"}

    # Starter has no free credits -> plan credit redemption is refused
    refused = client_a.post(
        reverse("boost-checkout"), {"boost_type": "area_7d", "use_plan_credit": True}, format="json", **hdr_a
    )
    assert refused.status_code == 403

    # Pay NGN 2,000 for an area boost; stays pending until webhook
    created = client_a.post(reverse("boost-checkout"), {"boost_type": "area_7d"}, format="json", **hdr_a)
    assert created.status_code == 201
    assert created.data["boost"]["status"] == "pending_payment"
    ref = created.data["transaction"]["reference"]
    assert ref.startswith("BST-")
    assert not any(r["is_featured"] for r in pub.get(reverse("marketplace-artisans")).data)

    hook = _signed_post(
        pub, settings, {"event": "charge.success", "data": {"reference": ref, "amount": 200000, "currency": "NGN"}}
    )
    assert hook.status_code == 200
    rows = pub.get(reverse("marketplace-artisans")).data
    assert rows[0]["organization_name"] == "Alpha Tailors"
    assert rows[0]["is_featured"] is True
    assert rows[0]["boost_badge"] == "Featured Nearby"
    # Idempotent replay
    assert _signed_post(
        pub, settings, {"event": "charge.success", "data": {"reference": ref, "amount": 200000, "currency": "NGN"}}
    ).status_code == 200
    assert MarketplaceBoost.objects.filter(organization=org_a, status="active").count() == 1

    # Product boost needs a published product of own workspace
    bad_prod = client_a.post(reverse("boost-checkout"), {"boost_type": "product_7d"}, format="json", **hdr_a)
    assert bad_prod.status_code == 400

    # Growth plan includes 1 free boost per month -> activates instantly at NGN 0, second is refused
    from billing.models import Subscription

    sub = Subscription.objects.get(organization=org_a)
    sub.plan = plans["growth"]
    sub.save(update_fields=["plan"])
    free = client_a.post(
        reverse("boost-checkout"),
        {"boost_type": "product_7d", "product": str(product.id), "use_plan_credit": True},
        format="json",
        **hdr_a,
    )
    assert free.status_code == 201
    assert free.data["boost"]["status"] == "active"
    assert free.data["boost"]["used_plan_credit"] is True
    again = client_a.post(
        reverse("boost-checkout"),
        {"boost_type": "area_7d", "use_plan_credit": True},
        format="json",
        **hdr_a,
    )
    assert again.status_code == 403

    goods = pub.get(reverse("marketplace-products")).data
    assert goods[0]["boost_badge"] == "Featured Listing"

    summary = get_platform_revenue_summary()
    assert summary["boost_revenue_total"] == Decimal("2000.00")
    assert summary["active_boosts_count"] == 2


@pytest.mark.django_db
def test_platform_admin_revenue_endpoint_and_neighborhood_limit_enforced():
    seed_default_plans()
    admin = User.objects.create_user(
        email="rev.admin@artisanos.io",
        password="StrongPassword123!",
        full_name="Admin",
        is_platform_admin=True,
    )
    adm = APIClient()
    adm.force_authenticate(user=admin)
    res = adm.get(reverse("platform-admin-revenue"))
    assert res.status_code == 200
    assert res.data["currency"] == "NGN"
    assert len(res.data["plan_breakdown"]) == 4

    _user, _org, client, hdr = _owner_client("lim@rev.ng", "Limit Workshop")
    assert client.get(reverse("platform-admin-revenue"), **hdr).status_code == 403

    # Starter covers 1 neighborhood: selecting 2 extra wards is refused
    from locations.seed import seed_nigeria_locations
    from locations.models import NigerianWard

    seed_nigeria_locations()
    w1, w2 = list(NigerianWard.objects.all()[:2])
    org_id = hdr["HTTP_X_ORGANIZATION_ID"]
    patch = client.patch(
        reverse("organization-detail", args=[org_id]),
        {"service_wards": [str(w1.id), str(w2.id)]},
        format="json",
        **hdr,
    )
    assert patch.status_code == 403
    assert PaymentTransaction.objects.count() == 0
    assert Plan.objects.get(code="starter").max_service_wards == 1


@pytest.mark.django_db
def test_payment_verify_ownership_escrow_pin_delivery_and_callback_validation(settings, monkeypatch):
    settings.PAYSTACK_SECRET_KEY = "sk_test_verify_secret"
    settings.FRONTEND_SITE_URL = "https://app.artisanos.ng"
    seed_default_plans()

    _owner_a, org_a, client_a, hdr_a = _owner_client("verify.a@rev.ng", "Alpha Studio")
    _owner_b, _org_b, client_b, _hdr_b = _owner_client("verify.b@rev.ng", "Beta Studio")

    # Open-redirect protection on callback_url
    bad_cb = client_a.post(
        reverse("subscription-checkout"),
        {"plan_code": "solo_pro", "billing_cycle": "monthly", "callback_url": "https://evil.example/steal"},
        format="json",
        **hdr_a,
    )
    assert bad_cb.status_code == 400

    # Valid trusted callback_url succeeds
    good_cb = client_a.post(
        reverse("subscription-checkout"),
        {"plan_code": "solo_pro", "billing_cycle": "monthly", "callback_url": "https://app.artisanos.ng/billing"},
        format="json",
        **hdr_a,
    )
    assert good_cb.status_code == 201
    sub_ref = good_cb.data["reference"]

    # Another tenant CANNOT verify Alpha Studio's reference (IDOR protection)
    monkeypatch.setattr(
        "billing.services.verify_paystack_transaction",
        lambda ref: {"reference": ref, "status": "success", "amount": 350000, "currency": "NGN"},
    )
    idor = client_b.post(reverse("subscription-verify-payment"), {"reference": sub_ref}, format="json")
    assert idor.status_code == 403

    # Owner A verifies their own subscription reference cleanly
    ok_sub = client_a.post(reverse("subscription-verify-payment"), {"reference": sub_ref}, format="json")
    assert ok_sub.status_code == 200
    assert ok_sub.data["processed"] is True

    # Escrow Paystack verification delivers 6-digit Completion PIN once to customer even if webhook arrived first
    from escrow.models import EscrowTransaction
    from escrow.services import create_escrow_contract

    org_a.is_verified = True
    org_a.save(update_fields=["is_verified"])
    customer = User.objects.create_user(
        email="buyer.verify@rev.ng",
        password="StrongPassword123!",
        full_name="Ada Buyer",
    )
    cust_client = APIClient()
    cust_client.force_authenticate(user=customer)

    # Org A is now on Solo Pro (2.5% artisan fee)
    escrow = create_escrow_contract(
        customer_user=customer,
        organization=org_a,
        job_title="Custom Kaftan",
        total_amount=Decimal("40000.00"),
    )
    assert escrow.artisan_fee_rate_pct == Decimal("2.50")
    assert escrow.total_payable_amount == Decimal("40800.00")

    # Simulate Paystack webhook arriving BEFORE customer returns to /escrow
    pub = APIClient()
    wh = _signed_post(
        pub,
        settings,
        {"event": "charge.success", "data": {"reference": escrow.reference, "amount": 4080000, "currency": "NGN"}},
    )
    assert wh.status_code == 200

    monkeypatch.setattr(
        "billing.services.verify_paystack_transaction",
        lambda ref: {"reference": ref, "status": "success", "amount": 4080000, "currency": "NGN"},
    )

    # Unrelated user cannot verify this escrow reference
    assert client_b.post(reverse("subscription-verify-payment"), {"reference": escrow.reference}, format="json").status_code == 403

    # Artisan member can verify status, but NEVER receives the customer's Completion PIN
    art_verify = client_a.post(reverse("subscription-verify-payment"), {"reference": escrow.reference}, format="json")
    assert art_verify.status_code == 200
    assert not art_verify.data.get("completion_pin")

    # Customer verifies upon redirect and receives their working 6-digit Completion PIN once
    cust_verify = cust_client.post(reverse("subscription-verify-payment"), {"reference": escrow.reference}, format="json")
    assert cust_verify.status_code == 200
    pin = cust_verify.data.get("completion_pin", "")
    assert len(pin) == 6
    assert str(cust_verify.data.get("escrow_id")) == str(escrow.id)

    # Replay does not re-expose or rotate the PIN
    replay = cust_client.post(reverse("subscription-verify-payment"), {"reference": escrow.reference}, format="json")
    assert replay.status_code == 200
    assert not replay.data.get("completion_pin")

    # The delivered PIN actually unlocks escrow release!
    rel = cust_client.post(
        reverse("escrow-release", args=[escrow.id]),
        {"completion_pin": pin},
        format="json",
    )
    assert rel.status_code == 200
    assert EscrowTransaction.objects.get(id=escrow.id).status == EscrowTransaction.Status.RELEASED
