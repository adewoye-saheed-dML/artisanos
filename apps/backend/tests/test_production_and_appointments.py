from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from customers.models import Customer
from orders.models import Order
from organizations.models import Membership
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_production_checklist_kanban_board_and_appointments_workflow():
    owner = User.objects.create_user(email="prod@atelier.ng", password="StrongPassword123!", full_name="Head Tailor")
    org, _ = create_organization_with_owner(user=owner, name="Victoria Bespoke")
    customer = Customer.objects.create(organization=org, full_name="Sade Ade", phone="+2348044445555", created_by=owner)
    order = Order.objects.create(
        organization=org,
        customer=customer,
        order_number="ORD-2026-0001",
        garment_type="Velvet Dinner Jacket",
        status=Order.Status.IN_PRODUCTION,
        assigned_to=owner,
        created_by=owner,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    headers = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    # Seed standard tailoring checklist
    seed_res = client.post(reverse("production-seed-checklist", args=[order.id]), {}, format="json", **headers)
    assert seed_res.status_code == 201
    assert len(seed_res.data) == 5
    first_task_id = seed_res.data[0]["id"]

    # Mark first task done
    done_res = client.patch(
        reverse("production-task-detail", args=[first_task_id]),
        {"status": "done"},
        format="json",
        **headers,
    )
    assert done_res.status_code == 200
    assert done_res.data["completed_at"] is not None

    # Flag an alteration task
    alt_res = client.post(
        reverse("production-task-list"),
        {
            "order": str(order.id),
            "title": "Taper left sleeve by 1.5 cm",
            "stage": "alteration",
            "is_alteration": True,
            "assigned_to": str(owner.id),
        },
        format="json",
        **headers,
    )
    assert alt_res.status_code == 201

    # Kanban board returns grouped column with accurate counts
    board_res = client.get(reverse("production-board"), **headers)
    assert board_res.status_code == 200
    in_prod_col = next(c for c in board_res.data["columns"] if c["status"] == "in_production")
    assert len(in_prod_col["orders"]) == 1
    card = in_prod_col["orders"][0]
    assert card["total_tasks"] == 6
    assert card["completed_tasks"] == 1
    assert card["alteration_tasks"] == 1

    # Schedule an upcoming fitting appointment
    future_time = (timezone.now() + timedelta(days=2)).isoformat()
    appt_res = client.post(
        reverse("appointment-list"),
        {
            "customer": str(customer.id),
            "order": str(order.id),
            "appointment_type": "first_fitting",
            "title": "First Jacket Fitting",
            "scheduled_at": future_time,
            "duration_minutes": 45,
            "location": "Main Fitting Room",
            "assigned_to": str(owner.id),
        },
        format="json",
        **headers,
    )
    assert appt_res.status_code == 201
    appt_id = appt_res.data["id"]

    # Dashboard reflects upcoming appointment count and list
    dash_res = client.get(reverse("dashboard-summary"), **headers)
    assert dash_res.status_code == 200
    assert dash_res.data["metrics"]["upcoming_appointments"] == 1
    assert len(dash_res.data["upcoming_appointments"]) == 1

    # Complete appointment
    comp_res = client.post(reverse("appointment-complete", args=[appt_id]), {}, format="json", **headers)
    assert comp_res.status_code == 200
    assert comp_res.data["status"] == "completed"


@pytest.mark.django_db
def test_production_appointments_tenant_isolation_and_customer_archive_rbac():
    owner_a = User.objects.create_user(email="a_ops@atelier.ng", password="StrongPassword123!", full_name="Owner A")
    artisan_a = User.objects.create_user(email="art_a@atelier.ng", password="StrongPassword123!", full_name="Artisan A")
    owner_b = User.objects.create_user(email="b_ops@atelier.ng", password="StrongPassword123!", full_name="Owner B")
    org_a, _ = create_organization_with_owner(user=owner_a, name="Org A")
    org_b, _ = create_organization_with_owner(user=owner_b, name="Org B")
    Membership.objects.create(user=artisan_a, organization=org_a, role=Membership.Role.ARTISAN, status=Membership.Status.ACTIVE)

    cust_a = Customer.objects.create(organization=org_a, full_name="Client A", phone="+2348010000001", created_by=owner_a)
    cust_b = Customer.objects.create(organization=org_b, full_name="Client B", phone="+2348010000002", created_by=owner_b)
    order_b = Order.objects.create(
        organization=org_b,
        customer=cust_b,
        order_number="ORD-2026-0009",
        garment_type="Coat",
        status=Order.Status.CONFIRMED,
        created_by=owner_b,
    )

    client_a = APIClient()
    client_a.force_authenticate(user=owner_a)
    hdr_a = {"HTTP_X_ORGANIZATION_ID": str(org_a.id)}

    # Org A cannot create task on Org B's order
    bad_task = client_a.post(
        reverse("production-task-list"),
        {"order": str(order_b.id), "title": "Unauthorized cut"},
        format="json",
        **hdr_a,
    )
    assert bad_task.status_code == 403

    # Org A cannot schedule appointment for Org B's customer
    bad_appt = client_a.post(
        reverse("appointment-list"),
        {
            "customer": str(cust_b.id),
            "title": "Cross-tenant fitting",
            "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
        },
        format="json",
        **hdr_a,
    )
    assert bad_appt.status_code == 403

    # Artisan cannot archive customer via PATCH, but Owner can archive and restore
    art_client = APIClient()
    art_client.force_authenticate(user=artisan_a)
    art_archive = art_client.patch(
        reverse("customer-detail", args=[cust_a.id]),
        {"is_archived": True},
        format="json",
        **hdr_a,
    )
    assert art_archive.status_code == 403

    owner_archive = client_a.delete(reverse("customer-detail", args=[cust_a.id]), **hdr_a)
    assert owner_archive.status_code == 200
    assert owner_archive.data["is_archived"] is True

    owner_restore = client_a.patch(
        reverse("customer-detail", args=[cust_a.id]),
        {"is_archived": False, "notes": "Restored active client"},
        format="json",
        **hdr_a,
    )
    assert owner_restore.status_code == 200
    assert owner_restore.data["is_archived"] is False
    assert owner_restore.data["notes"] == "Restored active client"
