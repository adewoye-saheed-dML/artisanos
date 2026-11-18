from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import Customer
from orders.models import Order
from organizations.models import Membership
from organizations.services import create_organization_with_owner
from production.models import ProductionTask


@pytest.mark.django_db
def test_analytics_overview_csv_exports_rbac_and_formula_injection_protection():
    owner = User.objects.create_user(email="ana@atelier.ng", password="StrongPassword123!", full_name="Owner")
    artisan = User.objects.create_user(email="art_ana@atelier.ng", password="StrongPassword123!", full_name="Artisan")
    org, _ = create_organization_with_owner(user=owner, name="Analytics Atelier", currency="NGN")
    Membership.objects.create(user=artisan, organization=org, role=Membership.Role.ARTISAN, status=Membership.Status.ACTIVE)

    # Include a spreadsheet formula injection attempt in customer notes
    customer = Customer.objects.create(
        organization=org,
        full_name="=HYPERLINK(\"http://evil\",\"Click\")",
        phone="+2348090001111",
        notes="+SUM(A1:A5)",
        created_by=owner,
    )
    order = Order.objects.create(
        organization=org,
        customer=customer,
        order_number="ORD-2026-0042",
        garment_type="Bespoke Tuxedo",
        status=Order.Status.IN_PRODUCTION,
        quoted_amount=Decimal("200000.00"),
        deposit_amount=Decimal("100000.00"),
        currency="NGN",
        created_by=owner,
    )
    ProductionTask.objects.create(
        organization=org,
        order=order,
        title="Cut lapel",
        status=ProductionTask.Status.DONE,
    )
    ProductionTask.objects.create(
        organization=org,
        order=order,
        title="Adjust sleeve",
        is_alteration=True,
        status=ProductionTask.Status.TODO,
    )

    owner_client = APIClient()
    owner_client.force_authenticate(user=owner)
    hdr = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    ov = owner_client.get(reverse("analytics-overview"), **hdr)
    assert ov.status_code == 200
    assert ov.data["currency"] == "NGN"
    assert ov.data["production"]["total_tasks"] == 2
    assert ov.data["production"]["completed_tasks"] == 1
    assert ov.data["production"]["completion_rate_pct"] == 50
    assert ov.data["production"]["open_alterations"] == 1
    assert ov.data["top_garment_types"][0]["garment_type"] == "Bespoke Tuxedo"
    assert len(ov.data["monthly_revenue_trend"]) == 1
    assert ov.data["monthly_revenue_trend"][0]["deposits_collected"] == "100000.00"

    # Artisan cannot export bulk CSV
    art_client = APIClient()
    art_client.force_authenticate(user=artisan)
    assert art_client.get(reverse("analytics-export-customers"), **hdr).status_code == 403
    assert art_client.get(reverse("analytics-export-orders"), **hdr).status_code == 403

    # Owner exports CSV with formula injection neutralized
    cust_csv = owner_client.get(reverse("analytics-export-customers"), **hdr)
    assert cust_csv.status_code == 200
    assert "text/csv" in cust_csv["Content-Type"]
    body = cust_csv.content.decode("utf-8")
    assert "'=HYPERLINK" in body
    assert "'+SUM(A1:A5)" in body

    ord_csv = owner_client.get(reverse("analytics-export-orders"), **hdr)
    assert ord_csv.status_code == 200
    assert "ORD-2026-0042" in ord_csv.content.decode("utf-8")


@pytest.mark.django_db
def test_seed_demo_data_command_is_idempotent():
    call_command("seed_demo_data")
    first_order_count = Order.objects.count()
    first_customer_count = Customer.objects.count()
    assert first_order_count >= 2
    assert first_customer_count >= 3

    # Re-running must not duplicate demo records
    call_command("seed_demo_data")
    assert Order.objects.count() == first_order_count
    assert Customer.objects.count() == first_customer_count
