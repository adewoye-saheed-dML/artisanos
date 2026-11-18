import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import Customer
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.services import create_measurement_profile, revise_measurement_profile
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_order_lifecycle_timeline_and_measurement_snapshot_preservation():
    seed_system_templates()
    tailoring_v1 = MeasurementTemplateVersion.objects.get(
        template__slug="standard-tailoring",
        version_number=1,
    )
    user = User.objects.create_user(email="orders@test.com", password="StrongPassword123!", full_name="Order Master")
    org, _ = create_organization_with_owner(user=user, name="Savile Lagos", currency="NGN")
    customer = Customer.objects.create(organization=org, full_name="Ngozi Eze", phone="+2348033333333", created_by=user)

    profile_v1 = create_measurement_profile(
        organization=org,
        customer=customer,
        template_version=tailoring_v1,
        unit_system="cm",
        status="verified",
        values_payload=[
            {"field_key": "neck", "numeric_value": "37.0"},
            {"field_key": "chest", "numeric_value": "94.0"},
            {"field_key": "waist", "numeric_value": "76.0"},
            {"field_key": "hip", "numeric_value": "98.0"},
            {"field_key": "shoulder_width", "numeric_value": "41.0"},
            {"field_key": "sleeve_length", "numeric_value": "59.0"},
        ],
        created_by=user,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    headers = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    order_res = client.post(
        reverse("order-list"),
        {
            "customer": str(customer.id),
            "garment_type": "Two-Piece Women's Suit",
            "measurement_profile": str(profile_v1.id),
            "quoted_amount": "120000.00",
            "deposit_amount": "60000.00",
            "status": "quoted",
        },
        format="json",
        **headers,
    )
    assert order_res.status_code == 201
    order_id = order_res.data["id"]
    assert order_res.data["payment_status"] == "partial"
    assert order_res.data["order_number"].startswith("ORD-")
    assert len(order_res.data["status_events"]) == 1

    # Invalid transition quoted -> completed must fail
    invalid_res = client.post(
        reverse("order-transition", args=[order_id]),
        {"to_status": "completed"},
        format="json",
        **headers,
    )
    assert invalid_res.status_code == 400

    # Valid transition quoted -> confirmed freezes snapshot
    confirm_res = client.post(
        reverse("order-transition", args=[order_id]),
        {"to_status": "confirmed", "notes": "Customer approved fabric and quote"},
        format="json",
        **headers,
    )
    assert confirm_res.status_code == 200
    assert confirm_res.data["status"] == "confirmed"
    assert confirm_res.data["measurement_snapshot"]["version_number"] == 1

    # Revising customer measurement profile afterwards must NOT alter confirmed order's snapshot
    revise_measurement_profile(
        profile=profile_v1,
        actor=user,
        values_payload=[
            {"field_key": "neck", "numeric_value": "38.0"},
            {"field_key": "chest", "numeric_value": "99.0"},
            {"field_key": "waist", "numeric_value": "80.0"},
            {"field_key": "hip", "numeric_value": "101.0"},
            {"field_key": "shoulder_width", "numeric_value": "42.0"},
            {"field_key": "sleeve_length", "numeric_value": "60.0"},
        ],
    )

    order_detail = client.get(reverse("order-detail", args=[order_id]), **headers)
    assert order_detail.status_code == 200
    chest_snapshot = next(
        v for v in order_detail.data["measurement_snapshot"]["values"] if v["field_key"] == "chest"
    )
    assert chest_snapshot["numeric_value"] == "94.00"

    # Dashboard summary reflects real DB counts
    dash_res = client.get(reverse("dashboard-summary"), **headers)
    assert dash_res.status_code == 200
    assert dash_res.data["metrics"]["total_customers"] == 1
    assert dash_res.data["metrics"]["active_orders"] == 1
    assert dash_res.data["metrics"]["monthly_recorded_deposits"] == "60000.00"
