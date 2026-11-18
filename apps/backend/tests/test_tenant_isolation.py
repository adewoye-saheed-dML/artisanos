import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import Customer
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.services import create_measurement_profile
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_cross_tenant_isolation_enforced_for_customers_measurements_and_orders():
    seed_system_templates()
    tailoring_v1 = MeasurementTemplateVersion.objects.get(
        template__slug="standard-tailoring",
        version_number=1,
    )

    user_a = User.objects.create_user(email="a@tailor.com", password="StrongPassword123!", full_name="User A")
    user_b = User.objects.create_user(email="b@tailor.com", password="StrongPassword123!", full_name="User B")
    org_a, _ = create_organization_with_owner(user=user_a, name="Atelier A")
    org_b, _ = create_organization_with_owner(user=user_b, name="Atelier B")

    customer_b = Customer.objects.create(
        organization=org_b,
        full_name="Secret Customer B",
        phone="+2348000000002",
        created_by=user_b,
    )
    profile_b = create_measurement_profile(
        organization=org_b,
        customer=customer_b,
        template_version=tailoring_v1,
        unit_system="cm",
        status="verified",
        values_payload=[
            {"field_key": "neck", "numeric_value": "39.0"},
            {"field_key": "chest", "numeric_value": "102.0"},
            {"field_key": "waist", "numeric_value": "86.0"},
            {"field_key": "hip", "numeric_value": "100.0"},
            {"field_key": "shoulder_width", "numeric_value": "45.0"},
            {"field_key": "sleeve_length", "numeric_value": "63.0"},
        ],
        created_by=user_b,
    )

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)

    # 1. Supplying Org B's header as User A must fail with 403
    spoof_res = client_a.get(reverse("customer-list"), HTTP_X_ORGANIZATION_ID=str(org_b.id))
    assert spoof_res.status_code == 403

    # 2. Using Org A's header, User A cannot list or retrieve Customer B
    list_res = client_a.get(reverse("customer-list"), HTTP_X_ORGANIZATION_ID=str(org_a.id))
    assert list_res.status_code == 200
    assert list_res.data["count"] == 0

    detail_res = client_a.get(
        reverse("customer-detail", args=[customer_b.id]),
        HTTP_X_ORGANIZATION_ID=str(org_a.id),
    )
    assert detail_res.status_code == 404

    # 3. User A cannot create an order referencing Customer B or Profile B
    order_res = client_a.post(
        reverse("order-list"),
        {
            "customer": str(customer_b.id),
            "garment_type": "Suit",
            "measurement_profile": str(profile_b.id),
            "quoted_amount": "50000.00",
        },
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org_a.id),
    )
    assert order_res.status_code == 403

    # 4. User A's customer cannot be paired with Org B's profile
    customer_a = Customer.objects.create(
        organization=org_a,
        full_name="Customer A",
        phone="+2348000000001",
        created_by=user_a,
    )
    cross_profile_order = client_a.post(
        reverse("order-list"),
        {
            "customer": str(customer_a.id),
            "garment_type": "Suit",
            "measurement_profile": str(profile_b.id),
            "quoted_amount": "50000.00",
        },
        format="json",
        HTTP_X_ORGANIZATION_ID=str(org_a.id),
    )
    assert cross_profile_order.status_code == 403
