import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import ConsentRecord, Customer
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.services import create_measurement_profile
from organizations.models import Organization
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_leatherwork_template_clone_versioning_and_category_order_checklist():
    seed_system_templates()
    owner = User.objects.create_user(email="shoe@craft.ng", password="StrongPassword123!", full_name="Master Cobbler")
    org, _ = create_organization_with_owner(
        user=owner,
        name="Abuja Bespoke Shoes",
        category=Organization.Category.SHOEMAKER,
    )
    customer = Customer.objects.create(organization=org, full_name="Ibrahim Musa", phone="+2348055551111", created_by=owner)

    client = APIClient()
    client.force_authenticate(user=owner)
    hdr = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    # All 3 system templates exist
    tpl_res = client.get(reverse("measurement-template-list"), **hdr)
    assert tpl_res.status_code == 200
    by_slug = {t["slug"]: t for t in tpl_res.data["results"]}
    assert "standard-tailoring" in by_slug
    assert "standard-shoemaking" in by_slug
    assert "standard-leatherwork" in by_slug

    # Clone system shoemaking template into a custom org template
    shoe_id = by_slug["standard-shoemaking"]["id"]
    clone_res = client.post(
        reverse("measurement-template-clone", args=[shoe_id]),
        {"name": "Bespoke Oxford Last"},
        format="json",
        **hdr,
    )
    assert clone_res.status_code == 201
    custom_id = clone_res.data["id"]
    assert clone_res.data["is_system"] is False
    assert clone_res.data["latest_version"]["version_number"] == 1

    # Publish v2 with an additional arch_height field
    v2_fields = [
        {
            "key": f["key"],
            "label": f["label"],
            "unit_type": f["unit_type"],
            "default_unit": f["default_unit"],
            "min_value": f["min_value"],
            "max_value": f["max_value"],
            "is_required": f["is_required"],
            "display_order": f["display_order"],
            "guidance_text": f["guidance_text"],
        }
        for f in clone_res.data["latest_version"]["fields"]
    ]
    v2_fields.append(
        {
            "key": "arch_height",
            "label": "Arch Height",
            "unit_type": "length",
            "default_unit": "cm",
            "min_value": "1.00",
            "max_value": "10.00",
            "is_required": False,
            "display_order": 9,
            "guidance_text": "Height under the foot arch.",
        }
    )
    v2_res = client.post(
        reverse("measurement-template-versions", args=[custom_id]),
        {"changelog": "Added arch height", "fields": v2_fields},
        format="json",
        **hdr,
    )
    assert v2_res.status_code == 201
    assert v2_res.data["version_number"] == 2
    assert len(v2_res.data["fields"]) == 9

    # Create shoemaking order with category_options and seed shoemaker checklist
    ord_res = client.post(
        reverse("order-list"),
        {
            "customer": str(customer.id),
            "garment_type": "Hand-Welted Oxford",
            "status": "confirmed",
            "quoted_amount": "140000.00",
            "category_options": {
                "sole_type": "Goodyear Welted Leather",
                "toe_shape": "Almond Toe",
                "leather_grade": "Full-Grain Calfskin",
            },
        },
        format="json",
        **hdr,
    )
    assert ord_res.status_code == 201
    assert ord_res.data["category_options"]["sole_type"] == "Goodyear Welted Leather"

    seed_res = client.post(
        reverse("production-seed-checklist", args=[ord_res.data["id"]]),
        {},
        format="json",
        **hdr,
    )
    assert seed_res.status_code == 201
    titles = [t["title"] for t in seed_res.data]
    assert "Last selection & sole pattern" in titles


@pytest.mark.django_db
def test_consented_fit_passport_sharing_and_cross_org_portability_import():
    seed_system_templates()
    tailoring_v1 = MeasurementTemplateVersion.objects.get(
        template__slug="standard-tailoring",
        version_number=1,
    )

    owner_a = User.objects.create_user(email="org_a_fit@atelier.ng", password="StrongPassword123!", full_name="Tailor A")
    owner_b = User.objects.create_user(email="org_b_fit@atelier.ng", password="StrongPassword123!", full_name="Tailor B")
    org_a, _ = create_organization_with_owner(user=owner_a, name="Atelier A")
    org_b, _ = create_organization_with_owner(user=owner_b, name="Atelier B")

    cust_a = Customer.objects.create(organization=org_a, full_name="Zainab Bello", phone="+2348066667777", created_by=owner_a)
    cust_b = Customer.objects.create(organization=org_b, full_name="Zainab Bello", phone="+2348066667777", created_by=owner_b)

    profile_a = create_measurement_profile(
        organization=org_a,
        customer=cust_a,
        template_version=tailoring_v1,
        unit_system="cm",
        status="verified",
        label="Evening Gown Fit",
        values_payload=[
            {"field_key": "neck", "numeric_value": "36.0"},
            {"field_key": "chest", "numeric_value": "92.0"},
            {"field_key": "waist", "numeric_value": "74.0"},
            {"field_key": "hip", "numeric_value": "98.0"},
            {"field_key": "shoulder_width", "numeric_value": "40.0"},
            {"field_key": "sleeve_length", "numeric_value": "58.0"},
        ],
        created_by=owner_a,
    )

    client_a = APIClient()
    client_a.force_authenticate(user=owner_a)
    hdr_a = {"HTTP_X_ORGANIZATION_ID": str(org_a.id)}

    # Consent must be explicitly confirmed
    no_consent = client_a.post(
        reverse("measurement-share-list"),
        {"profile_id": str(profile_a.id), "consent_confirmed": False},
        format="json",
        **hdr_a,
    )
    assert no_consent.status_code == 400

    # Valid consented share link
    share_res = client_a.post(
        reverse("measurement-share-list"),
        {
            "profile_id": str(profile_a.id),
            "recipient_label": "Shared with Atelier B",
            "consent_confirmed": True,
        },
        format="json",
        **hdr_a,
    )
    assert share_res.status_code == 201
    raw_token = share_res.data["token"]
    share_id = share_res.data["id"]
    assert ConsentRecord.objects.filter(
        customer=cust_a,
        consent_type=ConsentRecord.ConsentType.MEASUREMENT_SHARING,
        granted=True,
    ).exists()

    # Public Fit Passport shows first name & values without leaking phone or internal UUID
    pub_client = APIClient()
    fit_res = pub_client.get(reverse("public-fit-passport", args=[raw_token]))
    assert fit_res.status_code == 200
    assert fit_res.data["customer_first_name"] == "Zainab"
    assert fit_res.data["issuing_organization"] == "Atelier A"
    assert "+2348066667777" not in str(fit_res.data)
    assert str(cust_a.id) not in str(fit_res.data)

    # Atelier B imports the consented Fit Passport into its own customer record as needs_review
    client_b = APIClient()
    client_b.force_authenticate(user=owner_b)
    hdr_b = {"HTTP_X_ORGANIZATION_ID": str(org_b.id)}

    import_res = client_b.post(
        reverse("customer-measurement-import-from-share", kwargs={"customer_id": cust_b.id}),
        {"token": f"https://example.com/fit/{raw_token}"},
        format="json",
        **hdr_b,
    )
    assert import_res.status_code == 201
    assert import_res.data["source"] == "imported"
    assert import_res.data["status"] == "needs_review"
    assert len(import_res.data["values"]) == 6

    # Revoking share link immediately blocks public view and import
    revoke_res = client_a.post(reverse("measurement-share-revoke", args=[share_id]), {}, format="json", **hdr_a)
    assert revoke_res.status_code == 200
    assert pub_client.get(reverse("public-fit-passport", args=[raw_token])).status_code == 400
