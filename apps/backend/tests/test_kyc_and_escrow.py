import hashlib
import hmac
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from billing.models import AuditLog
from escrow.models import EscrowTransaction
from locations.models import PollingUnit
from locations.seed import seed_nigeria_locations
from organizations.models import Organization


@pytest.mark.django_db
def test_strict_artisan_kyc_nin_cac_document_upload_admin_approval_and_scammer_nin_block():
    seed_nigeria_locations()
    pu = PollingUnit.objects.get(pu_code="LA/11/01/001")
    pub = APIClient()

    # 1. Missing NIN rejected on artisan registration
    no_nin = pub.post(
        reverse("auth-register"),
        {
            "email": "nonin@test.ng",
            "password": "StrongPassword123!",
            "full_name": "No NIN Artisan",
            "phone": "+2348011112222",
            "organization_name": "Unverified Electric",
            "organization_category": "electrician",
        },
        format="json",
    )
    assert no_nin.status_code == 400
    assert "nin" in no_nin.data

    # 2. Invalid CAC format rejected
    bad_cac = pub.post(
        reverse("auth-register"),
        {
            "email": "badcac@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Bad CAC Artisan",
            "phone": "+2348011112223",
            "organization_name": "Bad CAC Works",
            "organization_category": "electrician",
            "nin": "71234567890",
            "cac_number": "INVALID99",
        },
        format="json",
    )
    assert bad_cac.status_code == 400
    assert "cac_number" in bad_cac.data

    # 3. Valid NIN + CAC succeeds, creates pending_review KYC, and keeps storefront UNPUBLISHED
    reg = pub.post(
        reverse("auth-register"),
        {
            "email": "verified.artisan@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Chidi Electrician",
            "phone": "+2348011112224",
            "organization_name": "Chidi Verified Solar",
            "organization_category": "electrician",
            "polling_unit": str(pu.id),
            "nin": "71234567890",
            "cac_number": "RC1234567",
            "cac_business_name": "Chidi Verified Solar Ltd",
            "guarantor_name": "Mrs. Ngozi Okafor",
            "guarantor_phone": "+2348099991111",
            "bank_name": "Zenith Bank",
            "bank_account_number": "1012345678",
            "bank_account_name": "Chidi Verified Solar Ltd",
        },
        format="json",
    )
    assert reg.status_code == 201
    org_data = reg.data["user"]["memberships"][0]["organization"]
    org_id = org_data["id"]
    org_slug = org_data["slug"]
    assert org_data["verification_status"] == "pending_review"
    assert org_data["is_verified"] is False

    # Storefront is hidden from public until KYC approved
    assert pub.get(reverse("public-storefront-detail", args=[org_slug])).status_code == 404

    # Artisan cannot self-publish storefront before admin approval
    artisan_user = User.objects.get(email="verified.artisan@test.ng")
    art_client = APIClient()
    art_client.force_authenticate(user=artisan_user)
    hdr = {"HTTP_X_ORGANIZATION_ID": org_id}
    publish_attempt = art_client.patch(
        reverse("storefront-settings"),
        {"is_published": True},
        format="json",
        **hdr,
    )
    assert publish_attempt.status_code == 403

    # Artisan uploads NIN Slip PDF document
    fake_pdf = SimpleUploadedFile("nin_slip.pdf", b"%PDF-1.4 fake nin slip", content_type="application/pdf")
    upload_res = art_client.post(
        reverse("organization-verification-documents", args=[org_id]),
        {"document_type": "nin_slip", "file": fake_pdf},
        format="multipart",
    )
    assert upload_res.status_code == 201
    assert upload_res.data["document_type"] == "nin_slip"

    # Platform Admin inspects queue and approves KYC -> storefront goes live with NIN + CAC verified badges
    admin_user = User.objects.create_user(
        email="kyc.admin@artisanos.io",
        password="StrongPassword123!",
        full_name="KYC Officer",
        is_platform_admin=True,
    )
    adm_client = APIClient()
    adm_client.force_authenticate(user=admin_user)

    queue = adm_client.get(reverse("platform-admin-verifications"), {"status": "pending_review"})
    assert queue.status_code == 200
    assert any(item["organization_id"] == org_id and item["nin_masked"] == "*******7890" for item in queue.data)

    approve_res = adm_client.post(
        reverse("platform-admin-kyc-approve", args=[org_id]),
        {"reason": "NIN and CAC RC1234567 verified cleanly."},
        format="json",
    )
    assert approve_res.status_code == 200
    assert approve_res.data["status"] == "approved"
    assert AuditLog.objects.filter(organization_id=org_id, action="artisan_kyc_approved").exists()

    # Now storefront is live and shows cac_verified=True & is_verified=True
    live_sf = pub.get(reverse("public-storefront-detail", args=[org_slug]))
    assert live_sf.status_code == 200
    assert live_sf.data["storefront"]["is_verified"] is True
    assert live_sf.data["storefront"]["cac_verified"] is True

    # If org is suspended for scamming, another signup reusing the same NIN must be blocked!
    org_obj = Organization.objects.get(id=org_id)
    org_obj.is_active = False
    org_obj.save(update_fields=["is_active"])

    re_reg = pub.post(
        reverse("auth-register"),
        {
            "email": "scammer.retry@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Repeat Scammer",
            "phone": "+2348011119999",
            "organization_name": "New Fake Brand",
            "organization_category": "electrician",
            "nin": "71234567890",
        },
        format="json",
    )
    assert re_reg.status_code == 400
    assert "nin" in re_reg.data


@pytest.mark.django_db
def test_customer_escrow_full_lifecycle_pin_protection_dispute_and_paystack_webhook(settings):
    settings.PAYSTACK_SECRET_KEY = ""  # Start in sandbox mode
    seed_nigeria_locations()
    pu = PollingUnit.objects.get(pu_code="LA/11/01/001")

    admin_user = User.objects.create_user(
        email="escrow.admin@artisanos.io",
        password="StrongPassword123!",
        full_name="Escrow Admin",
        is_platform_admin=True,
    )
    pub = APIClient()

    # Register & approve artisan
    art_reg = pub.post(
        reverse("auth-register"),
        {
            "email": "escrow.plumber@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Sodiq Plumber",
            "phone": "+2348020001111",
            "organization_name": "Sodiq Verified Plumbing",
            "organization_category": "plumber",
            "polling_unit": str(pu.id),
            "nin": "81234567890",
            "cac_number": "BN3344556",
        },
        format="json",
    )
    assert art_reg.status_code == 201
    org_id = art_reg.data["user"]["memberships"][0]["organization"]["id"]
    org_slug = art_reg.data["user"]["memberships"][0]["organization"]["slug"]

    adm_client = APIClient()
    adm_client.force_authenticate(user=admin_user)
    assert adm_client.post(reverse("platform-admin-kyc-approve", args=[org_id]), {"reason": "Verified"}, format="json").status_code == 200

    # Register customer (no workspace required)
    cust_reg = pub.post(
        reverse("auth-register"),
        {
            "email": "escrow.customer@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Amaka Customer",
            "phone": "+2348090002222",
            "polling_unit": str(pu.id),
        },
        format="json",
    )
    assert cust_reg.status_code == 201

    customer = User.objects.get(email="escrow.customer@test.ng")
    artisan = User.objects.get(email="escrow.plumber@test.ng")

    cust_client = APIClient()
    cust_client.force_authenticate(user=customer)
    art_client = APIClient()
    art_client.force_authenticate(user=artisan)

    # 1. Customer opens escrow contract (0% advance -> 100% locked until completion!)
    create_res = cust_client.post(
        reverse("escrow-list-create"),
        {
            "organization_slug": org_slug,
            "job_title": "Replace Bathroom Concealed Shower & Pipes",
            "job_description": "Full bathroom pipe replacement and pressure test.",
            "total_amount": "50000.00",
            "materials_advance_pct": 0,
        },
        format="json",
    )
    assert create_res.status_code == 201
    escrow_id = create_res.data["id"]
    assert create_res.data["held_in_escrow_amount"] == "50000.00"
    assert create_res.data["status"] == "awaiting_funding"

    # 2. Customer funds escrow -> receives private 6-digit Completion PIN
    fund_res = cust_client.post(reverse("escrow-fund", args=[escrow_id]), {}, format="json")
    assert fund_res.status_code == 200
    pin = fund_res.data["completion_pin"]
    assert len(pin) == 6
    assert fund_res.data["escrow"]["status"] == "funded_held"

    # 3. Artisan CANNOT release escrow funds to themselves!
    self_release = art_client.post(
        reverse("escrow-release", args=[escrow_id]),
        {"completion_pin": pin},
        format="json",
    )
    assert self_release.status_code == 403

    # 4. Artisan completes work and submits for customer inspection
    submit_res = art_client.post(
        reverse("escrow-submit-work", args=[escrow_id]),
        {"completion_notes": "Installed brass mixer and pressure tested with zero leaks."},
        format="json",
    )
    assert submit_res.status_code == 200
    assert submit_res.data["status"] == "work_submitted"

    # 5. Wrong PIN rejected; correct PIN releases full payout to artisan!
    wrong_pin = cust_client.post(
        reverse("escrow-release", args=[escrow_id]),
        {"completion_pin": "000000"},
        format="json",
    )
    assert wrong_pin.status_code == 400

    release_res = cust_client.post(
        reverse("escrow-release", args=[escrow_id]),
        {"completion_pin": pin, "notes": "Inspected shower, works great!"},
        format="json",
    )
    assert release_res.status_code == 200
    assert release_res.data["status"] == "released"
    assert release_res.data["artisan_payout_amount"] == "48500.00"  # 50,000 - 3% fee

    # 6. Dispute & Paystack Webhook test on a second escrow contract
    settings.PAYSTACK_SECRET_KEY = "sk_test_escrow_webhook_secret"
    esc2_res = cust_client.post(
        reverse("escrow-list-create"),
        {
            "organization_slug": org_slug,
            "job_title": "Borehole Pump Overhaul",
            "total_amount": "30000.00",
        },
        format="json",
    )
    assert esc2_res.status_code == 201
    esc2_id = esc2_res.data["id"]
    esc2_ref = esc2_res.data["reference"]

    # Direct sandbox fund blocked when live PAYSTACK_SECRET_KEY is configured
    assert cust_client.post(reverse("escrow-fund", args=[esc2_id]), {}, format="json").status_code == 400

    # Valid Paystack HMAC-SHA512 webhook funds the escrow (30,000 + 600 buyer protection NGN -> 3,060,000 kobo)
    assert esc2_res.data["total_payable_amount"] == "30600.00"
    hook_payload = {
        "event": "charge.success",
        "data": {"reference": esc2_ref, "amount": 3060000, "currency": "NGN"},
    }
    raw_body = json.dumps(hook_payload).encode("utf-8")
    sig = hmac.new(settings.PAYSTACK_SECRET_KEY.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    hook_res = pub.post(
        reverse("paystack-webhook"),
        data=raw_body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert hook_res.status_code == 200
    assert EscrowTransaction.objects.get(id=esc2_id).status == EscrowTransaction.Status.FUNDED_HELD

    # Customer raises dispute -> funds frozen -> Platform Admin refunds customer
    dispute_res = cust_client.post(
        reverse("escrow-dispute", args=[esc2_id]),
        {"reason": "Artisan did not show up on the agreed date after funding."},
        format="json",
    )
    assert dispute_res.status_code == 200
    assert dispute_res.data["status"] == "disputed"

    resolve_res = adm_client.post(
        reverse("platform-admin-escrow-resolve", args=[esc2_id]),
        {"decision": "refund_customer", "reason": "Confirmed no-show; full refund authorized."},
        format="json",
    )
    assert resolve_res.status_code == 200
    assert resolve_res.data["status"] == "refunded"
    assert AuditLog.objects.filter(action="escrow_dispute_refund_customer", target_id=esc2_id).exists()
