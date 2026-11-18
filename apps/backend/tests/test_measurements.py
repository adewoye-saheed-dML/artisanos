from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import ConsentRecord, Customer
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.models import MeasurementProfile, MeasurementRequest
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_tailoring_and_shoemaking_templates_seeded_and_custom_template_supported():
    seed_system_templates()
    user = User.objects.create_user(email="tailor@test.com", password="StrongPassword123!", full_name="Tailor")
    org, _ = create_organization_with_owner(user=user, name="Bespoke Hub")

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get(reverse("measurement-template-list"), HTTP_X_ORGANIZATION_ID=str(org.id))
    assert res.status_code == 200
    slugs = {t["slug"]: t for t in res.data["results"]}
    assert "standard-tailoring" in slugs
    assert "standard-shoemaking" in slugs
    assert len(slugs["standard-tailoring"]["latest_version"]["fields"]) == 16

    # Create a custom leatherwork template without any schema changes
    custom_res = client.post(
        reverse("measurement-template-list"),
        {
            "name": "Custom Belt & Strap",
            "category": "leatherwork",
            "fields": [
                {
                    "key": "belt_waist",
                    "label": "Belt Waist",
                    "unit_type": "length",
                    "default_unit": "cm",
                    "min_value": "50.00",
                    "max_value": "180.00",
                    "is_required": True,
                    "display_order": 1,
                }
            ],
        },
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert custom_res.status_code == 201
    assert custom_res.data["is_system"] is False


@pytest.mark.django_db
def test_measurement_validation_unit_conversion_and_immutable_history():
    seed_system_templates()
    tailoring_v1 = MeasurementTemplateVersion.objects.get(
        template__slug="standard-tailoring",
        version_number=1,
    )
    user = User.objects.create_user(email="m@test.com", password="StrongPassword123!", full_name="Master Tailor")
    org, _ = create_organization_with_owner(user=user, name="Master Tailors")
    customer = Customer.objects.create(organization=org, full_name="Chidi Obi", phone="+2348011111111", created_by=user)

    client = APIClient()
    client.force_authenticate(user=user)
    url = reverse("customer-measurement-list", kwargs={"customer_id": customer.id})

    # Out-of-range chest in inches (10 in = 25.4 cm < 50 cm min) must fail
    bad_res = client.post(
        url,
        {
            "template_version_id": str(tailoring_v1.id),
            "unit_system": "in",
            "status": "verified",
            "values": [
                {"field_key": "neck", "numeric_value": "15.5"},
                {"field_key": "chest", "numeric_value": "10.0"},
                {"field_key": "waist", "numeric_value": "33.0"},
                {"field_key": "hip", "numeric_value": "39.0"},
                {"field_key": "shoulder_width", "numeric_value": "18.0"},
                {"field_key": "sleeve_length", "numeric_value": "25.0"},
            ],
        },
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert bad_res.status_code == 400

    # Valid inches measurement creates v1
    v1_res = client.post(
        url,
        {
            "template_version_id": str(tailoring_v1.id),
            "label": "Agbada Fit",
            "unit_system": "in",
            "status": "verified",
            "values": [
                {"field_key": "neck", "numeric_value": "15.5"},
                {"field_key": "chest", "numeric_value": "40.0"},
                {"field_key": "waist", "numeric_value": "34.0"},
                {"field_key": "hip", "numeric_value": "40.0"},
                {"field_key": "shoulder_width", "numeric_value": "18.0"},
                {"field_key": "sleeve_length", "numeric_value": "25.0"},
            ],
        },
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert v1_res.status_code == 201
    v1_id = v1_res.data["id"]
    assert v1_res.data["version_number"] == 1
    assert v1_res.data["is_latest"] is True

    # Editing v1 creates v2 and preserves v1 as superseded
    detail_url = reverse("customer-measurement-detail", kwargs={"customer_id": customer.id, "pk": v1_id})
    v2_res = client.patch(
        detail_url,
        {
            "unit_system": "cm",
            "notes": "Re-measured in cm",
            "values": [
                {"field_key": "neck", "numeric_value": "40.0"},
                {"field_key": "chest", "numeric_value": "104.0"},
                {"field_key": "waist", "numeric_value": "88.0"},
                {"field_key": "hip", "numeric_value": "102.0"},
                {"field_key": "shoulder_width", "numeric_value": "46.0"},
                {"field_key": "sleeve_length", "numeric_value": "64.0"},
            ],
        },
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert v2_res.status_code == 200
    assert v2_res.data["version_number"] == 2
    assert str(v2_res.data["parent_profile"]) == str(v1_id)
    assert v2_res.data["is_latest"] is True

    v1_obj = MeasurementProfile.objects.get(id=v1_id)
    assert v1_obj.status == MeasurementProfile.Status.SUPERSEDED
    assert v1_obj.is_latest is False


@pytest.mark.django_db
def test_measurement_request_public_submission_and_single_use():
    seed_system_templates()
    tailoring_v1 = MeasurementTemplateVersion.objects.get(
        template__slug="standard-tailoring",
        version_number=1,
    )
    user = User.objects.create_user(email="req@test.com", password="StrongPassword123!", full_name="Req Tailor")
    org, _ = create_organization_with_owner(user=user, name="Lagos Tailors")
    customer = Customer.objects.create(organization=org, full_name="Tunde Bakare", phone="+2348022222222", created_by=user)

    auth_client = APIClient()
    auth_client.force_authenticate(user=user)
    req_res = auth_client.post(
        reverse("measurement-request-list"),
        {"customer_id": str(customer.id), "template_version_id": str(tailoring_v1.id)},
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert req_res.status_code == 201
    token = req_res.data["token"]

    pub_client = APIClient()
    pub_url = reverse("public-measurement-request", kwargs={"token": token})
    get_res = pub_client.get(pub_url)
    assert get_res.status_code == 200
    assert get_res.data["customer_first_name"] == "Tunde"
    # Internal customer UUID must not be exposed
    assert str(customer.id) not in str(get_res.data)

    # Submission requires explicit consent
    no_consent = pub_client.post(
        pub_url,
        {
            "unit_system": "cm",
            "consent_granted": False,
            "values": [
                {"field_key": "neck", "numeric_value": "40.0"},
                {"field_key": "chest", "numeric_value": "102.0"},
                {"field_key": "waist", "numeric_value": "88.0"},
                {"field_key": "hip", "numeric_value": "100.0"},
                {"field_key": "shoulder_width", "numeric_value": "45.0"},
                {"field_key": "sleeve_length", "numeric_value": "63.0"},
            ],
        },
        format="json",
    )
    assert no_consent.status_code == 400

    # Valid submission creates 'submitted' (never 'verified') profile and records consent
    sub_res = pub_client.post(
        pub_url,
        {
            "unit_system": "cm",
            "consent_granted": True,
            "values": [
                {"field_key": "neck", "numeric_value": "40.0"},
                {"field_key": "chest", "numeric_value": "102.0"},
                {"field_key": "waist", "numeric_value": "88.0"},
                {"field_key": "hip", "numeric_value": "100.0"},
                {"field_key": "shoulder_width", "numeric_value": "45.0"},
                {"field_key": "sleeve_length", "numeric_value": "63.0"},
            ],
        },
        format="json",
    )
    assert sub_res.status_code == 201
    assert sub_res.data["status"] == "submitted"
    assert ConsentRecord.objects.filter(customer=customer, granted=True).exists()

    # Reuse of submitted token is blocked
    reuse_res = pub_client.get(pub_url)
    assert reuse_res.status_code == 410

    # Expired request is blocked
    req_obj = MeasurementRequest.objects.get(id=req_res.data["id"])
    req_obj.status = MeasurementRequest.Status.PENDING
    req_obj.expires_at = timezone.now() - timedelta(hours=1)
    req_obj.save()
    expired_res = pub_client.get(pub_url)
    assert expired_res.status_code == 410
