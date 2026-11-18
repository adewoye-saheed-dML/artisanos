import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Product
from notifications.models import Notification
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_product_inventory_ledger_public_storefront_inquiries_and_notifications():
    owner = User.objects.create_user(email="shop@atelier.ng", password="StrongPassword123!", full_name="Shop Owner")
    org, _ = create_organization_with_owner(user=owner, name="Lagos Velvet House", currency="NGN")

    client = APIClient()
    client.force_authenticate(user=owner)
    hdr = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    # Create published ready-made product with initial stock 4
    prod_res = client.post(
        reverse("product-list"),
        {
            "name": "Linen Resort Shirt",
            "category": "Ready-to-Wear",
            "product_type": "ready_made",
            "price": "45000.00",
            "status": "published",
            "track_inventory": True,
            "initial_stock": 4,
        },
        format="json",
        **hdr,
    )
    assert prod_res.status_code == 201
    prod_id = prod_res.data["id"]
    assert prod_res.data["stock_quantity"] == 4

    # Create draft product (must NOT appear on public storefront)
    draft_res = client.post(
        reverse("product-list"),
        {
            "name": "Unreleased Prototype Coat",
            "product_type": "made_to_order",
            "price": "180000.00",
            "status": "draft",
        },
        format="json",
        **hdr,
    )
    assert draft_res.status_code == 201

    # Direct PATCH must not silently overwrite stock_quantity
    patch_res = client.patch(
        reverse("product-detail", args=[prod_id]),
        {"stock_quantity": 999, "description": "Breathable cotton-linen blend"},
        format="json",
        **hdr,
    )
    assert patch_res.status_code == 200
    assert patch_res.data["stock_quantity"] == 4

    # Adjusting below 0 must fail
    over_sell = client.post(
        reverse("product-adjust-inventory-action", args=[prod_id]),
        {"movement_type": "sale", "quantity_delta": -10, "reason": "Oversell test"},
        format="json",
        **hdr,
    )
    assert over_sell.status_code == 400

    # Valid sale (-2 -> balance 2) records movement and triggers low-stock notification
    sale_res = client.post(
        reverse("product-adjust-inventory-action", args=[prod_id]),
        {"movement_type": "sale", "quantity_delta": -2, "reason": "Walk-in sale"},
        format="json",
        **hdr,
    )
    assert sale_res.status_code == 201
    assert sale_res.data["balance_after"] == 2

    # Ledger has 2 entries (initial + sale)
    mov_res = client.get(reverse("product-movements", args=[prod_id]), **hdr)
    assert mov_res.status_code == 200
    assert len(mov_res.data) == 2

    # Public storefront shows only the published product
    pub_client = APIClient()
    sf_res = pub_client.get(reverse("public-storefront-detail", args=[org.slug]))
    assert sf_res.status_code == 200
    assert sf_res.data["storefront"]["organization_name"] == "Lagos Velvet House"
    assert len(sf_res.data["products"]) == 1
    assert sf_res.data["products"][0]["name"] == "Linen Resort Shirt"

    # Public buyer submits inquiry
    inq_res = pub_client.post(
        reverse("public-storefront-inquiry", args=[org.slug]),
        {
            "product": prod_id,
            "buyer_name": "Amaka Obi",
            "buyer_phone": "+2348091112222",
            "message": "Do you have size Large in ivory?",
        },
        format="json",
    )
    assert inq_res.status_code == 201
    assert inq_res.data["status"] == "new"

    # Notifications endpoint shows both low_stock and storefront_inquiry as unread
    notif_res = client.get(reverse("notification-list"), **hdr)
    assert notif_res.status_code == 200
    assert notif_res.data["unread_count"] == 2
    types = {n["event_type"] for n in notif_res.data["results"]}
    assert Notification.EventType.LOW_STOCK in types
    assert Notification.EventType.STOREFRONT_INQUIRY in types

    # Mark all read clears unread count
    read_all = client.post(reverse("notification-read-all"), {}, format="json", **hdr)
    assert read_all.status_code == 200
    assert read_all.data["updated"] == 2
    assert client.get(reverse("notification-list"), **hdr).data["unread_count"] == 0


@pytest.mark.django_db
def test_catalog_and_notifications_tenant_isolation():
    user_a = User.objects.create_user(email="cat_a@atelier.ng", password="StrongPassword123!", full_name="Owner A")
    user_b = User.objects.create_user(email="cat_b@atelier.ng", password="StrongPassword123!", full_name="Owner B")
    org_a, _ = create_organization_with_owner(user=user_a, name="Store A")
    org_b, _ = create_organization_with_owner(user=user_b, name="Store B")

    prod_b = Product.objects.create(
        organization=org_b,
        name="Secret Bag B",
        slug="secret-bag-b",
        price="90000.00",
        status=Product.Status.PUBLISHED,
        stock_quantity=5,
        created_by=user_b,
    )
    Notification.objects.create(
        organization=org_b,
        event_type=Notification.EventType.SYSTEM,
        title="Private Org B Alert",
    )

    client_a = APIClient()
    client_a.force_authenticate(user=user_a)
    hdr_a = {"HTTP_X_ORGANIZATION_ID": str(org_a.id)}

    assert client_a.get(reverse("product-detail", args=[prod_b.id]), **hdr_a).status_code == 404
    assert client_a.get(reverse("notification-list"), **hdr_a).data["unread_count"] == 0

    # Public inquiry against Org A cannot reference Org B's product
    pub_client = APIClient()
    cross_inq = pub_client.post(
        reverse("public-storefront-inquiry", args=[org_a.slug]),
        {
            "product": str(prod_b.id),
            "buyer_name": "Buyer",
            "buyer_phone": "+2348000000000",
            "message": "Trying to reference another store's product",
        },
        format="json",
    )
    assert cross_inq.status_code == 400
