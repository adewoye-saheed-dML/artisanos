from datetime import timedelta
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import ConsentRecord, Customer
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.media_services import purge_expired_media_assets
from measurements.models import MediaAccessLog, MediaAsset
from organizations.models import Membership
from organizations.services import create_organization_with_owner

# Minimal valid JPEG header + EOI marker
SAMPLE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


@pytest.mark.django_db
def test_guided_capture_consent_rbac_audit_and_physical_deletion(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path

    owner = User.objects.create_user(email="cap_owner@atelier.ng", password="StrongPassword123!", full_name="Owner")
    assistant = User.objects.create_user(email="cap_sales@atelier.ng", password="StrongPassword123!", full_name="Sales")
    org, _ = create_organization_with_owner(user=owner, name="Fit Studio")
    Membership.objects.create(
        user=assistant,
        organization=org,
        role=Membership.Role.SALES_ASSISTANT,
        status=Membership.Status.ACTIVE,
    )
    customer = Customer.objects.create(organization=org, full_name="Kola Ade", phone="+2348077778888", created_by=owner)

    owner_client = APIClient()
    owner_client.force_authenticate(user=owner)
    hdr = {"HTTP_X_ORGANIZATION_ID": str(org.id)}
    list_url = reverse("customer-media-list", kwargs={"customer_id": customer.id})

    # 1. Missing photo consent rejected
    no_consent = owner_client.post(
        list_url,
        {
            "file": SimpleUploadedFile("front.jpg", SAMPLE_JPEG, content_type="image/jpeg"),
            "view_angle": "front",
            "photo_consent_granted": "false",
        },
        format="multipart",
        **hdr,
    )
    assert no_consent.status_code == 400

    # 2. Spoofed non-image bytes rejected
    fake_img = owner_client.post(
        list_url,
        {
            "file": SimpleUploadedFile("evil.jpg", b"<html>not an image</html>", content_type="image/jpeg"),
            "view_angle": "front",
            "photo_consent_granted": "true",
        },
        format="multipart",
        **hdr,
    )
    assert fake_img.status_code == 400

    # 3. Valid consented upload succeeds and records consent + uploaded log
    ok_res = owner_client.post(
        list_url,
        {
            "file": SimpleUploadedFile("front.jpg", SAMPLE_JPEG, content_type="image/jpeg"),
            "view_angle": "front",
            "photo_consent_granted": "true",
            "quality_metadata": '{"width": 720, "height": 1280, "brightness_score": 135}',
        },
        format="multipart",
        **hdr,
    )
    assert ok_res.status_code == 201
    asset_id = ok_res.data["id"]
    assert ok_res.data["allow_model_training"] is False
    assert ConsentRecord.objects.filter(
        customer=customer,
        consent_type=ConsentRecord.ConsentType.PHOTO_CAPTURE,
        granted=True,
    ).exists()

    asset = MediaAsset.objects.get(id=asset_id)
    stored_path = Path(asset.file.path)
    assert stored_path.exists()

    # 4. Sales assistant is blocked from viewing customer body photos
    sales_client = APIClient()
    sales_client.force_authenticate(user=assistant)
    assert sales_client.get(list_url, **hdr).status_code == 403
    content_url = reverse("customer-media-content", kwargs={"customer_id": customer.id, "pk": asset_id})
    assert sales_client.get(content_url, **hdr).status_code == 403

    # 5. Owner viewing photo streams bytes with private no-store cache header & writes audit log
    view_res = owner_client.get(content_url, **hdr)
    assert view_res.status_code == 200
    assert "no-store" in view_res["Cache-Control"]
    assert MediaAccessLog.objects.filter(asset=asset, action=MediaAccessLog.Action.VIEWED).exists()

    # 6. Permanent delete physically removes file from disk and blocks subsequent reads
    detail_url = reverse("customer-media-detail", kwargs={"customer_id": customer.id, "pk": asset_id})
    del_res = owner_client.delete(detail_url, **hdr)
    assert del_res.status_code == 200
    assert del_res.data["status"] == "deleted"
    assert not stored_path.exists()
    assert owner_client.get(content_url, **hdr).status_code == 410


@pytest.mark.django_db
def test_public_request_guided_photo_links_to_profile_and_retention_purge(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    seed_system_templates()
    tailoring_v1 = MeasurementTemplateVersion.objects.get(
        template__slug="standard-tailoring",
        version_number=1,
    )

    owner = User.objects.create_user(email="pubcap@atelier.ng", password="StrongPassword123!", full_name="Tailor")
    org, _ = create_organization_with_owner(user=owner, name="Lagos Fit")
    customer = Customer.objects.create(organization=org, full_name="Funke Akindele-Demo", phone="+2348088889999", created_by=owner)

    auth_client = APIClient()
    auth_client.force_authenticate(user=owner)
    hdr = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    req_res = auth_client.post(
        reverse("measurement-request-list"),
        {"customer_id": str(customer.id), "template_version_id": str(tailoring_v1.id)},
        format="json",
        **hdr,
    )
    token = req_res.data["token"]

    pub_client = APIClient()
    photo_res = pub_client.post(
        reverse("public-measurement-request-photos", kwargs={"token": token}),
        {
            "file": SimpleUploadedFile("side.jpg", SAMPLE_JPEG, content_type="image/jpeg"),
            "view_angle": "side",
            "photo_consent_granted": "true",
        },
        format="multipart",
    )
    assert photo_res.status_code == 201
    asset_id = photo_res.data["id"]

    # Customer submits manual measurements -> photo automatically linked to resulting profile
    sub_res = pub_client.post(
        reverse("public-measurement-request", kwargs={"token": token}),
        {
            "unit_system": "cm",
            "consent_granted": True,
            "values": [
                {"field_key": "neck", "numeric_value": "37.0"},
                {"field_key": "chest", "numeric_value": "94.0"},
                {"field_key": "waist", "numeric_value": "76.0"},
                {"field_key": "hip", "numeric_value": "99.0"},
                {"field_key": "shoulder_width", "numeric_value": "41.0"},
                {"field_key": "sleeve_length", "numeric_value": "59.0"},
            ],
        },
        format="json",
    )
    assert sub_res.status_code == 201

    asset = MediaAsset.objects.get(id=asset_id)
    assert asset.profile is not None
    stored_path = Path(asset.file.path)
    assert stored_path.exists()

    # Expire retention and run purge
    asset.retention_expires_at = timezone.now() - timedelta(days=1)
    asset.save(update_fields=["retention_expires_at"])
    purged_count = purge_expired_media_assets()
    assert purged_count == 1
    asset.refresh_from_db()
    assert asset.status == MediaAsset.Status.EXPIRED
    assert not stored_path.exists()
