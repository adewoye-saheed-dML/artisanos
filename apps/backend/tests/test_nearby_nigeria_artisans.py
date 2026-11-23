from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Product, Storefront, StorefrontInquiry
from catalog.services import get_or_create_storefront
from customers.models import Customer
from locations.models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from locations.seed import seed_nigeria_locations
from orders.models import Order
from organizations.kyc_services import approve_artisan_kyc
from organizations.models import Organization
from organizations.services import create_organization_with_owner


@pytest.mark.django_db
def test_nigeria_location_seed_cascade_and_unified_search():
    stats = seed_nigeria_locations()
    assert stats["total_states"] == 37
    assert stats["total_lgas"] == 774
    assert stats["total_polling_units"] >= 60

    pub = APIClient()

    states_res = pub.get(reverse("location-states"))
    assert states_res.status_code == 200
    assert len(states_res.data) == 37
    lagos = next(s for s in states_res.data if s["code"] == "LA")

    lgas_res = pub.get(reverse("location-lgas"), {"state": lagos["id"]})
    assert lgas_res.status_code == 200
    ikeja = next(l for l in lgas_res.data if l["name"] == "Ikeja")

    wards_res = pub.get(reverse("location-wards"), {"lga": ikeja["id"]})
    assert wards_res.status_code == 200
    anifowoshe = next(w for w in wards_res.data if "Anifowoshe" in w["name"])

    pus_res = pub.get(reverse("location-polling-units"), {"ward": anifowoshe["id"]})
    assert pus_res.status_code == 200
    assert any(p["pu_code"] == "LA/11/01/001" for p in pus_res.data)

    search_res = pub.get(reverse("location-search"), {"q": "Allen"})
    assert search_res.status_code == 200
    assert len(search_res.data["polling_units"]) >= 1
    assert any("Allen" in p["name"] or "Allen" in p["landmark"] for p in search_res.data["polling_units"])


@pytest.mark.django_db
def test_nearby_artisan_proximity_ranking_by_polling_unit_ward_coverage_and_lga():
    seed_nigeria_locations()

    pu_allen = PollingUnit.objects.get(pu_code="LA/11/01/001")  # Ikeja -> Anifowoshe
    pu_comp_village = PollingUnit.objects.get(pu_code="LA/11/01/002")  # Same Ward (Anifowoshe)
    pu_opebi = PollingUnit.objects.get(pu_code="LA/11/02/001")  # Different Ward (Opebi), same LGA (Ikeja)
    pu_alausa = PollingUnit.objects.get(pu_code="LA/11/03/001")  # Different Ward (Alausa), same LGA (Ikeja)
    pu_wuse = PollingUnit.objects.get(pu_code="FC/06/01/001")  # Different State (FCT Abuja)

    u1 = User.objects.create_user(email="e1@test.ng", password="StrongPassword123!", full_name="E1")
    u2 = User.objects.create_user(email="e2@test.ng", password="StrongPassword123!", full_name="E2")
    u3 = User.objects.create_user(email="e3@test.ng", password="StrongPassword123!", full_name="E3")
    u4 = User.objects.create_user(email="e4@test.ng", password="StrongPassword123!", full_name="E4")
    u5 = User.objects.create_user(email="e5@test.ng", password="StrongPassword123!", full_name="E5")

    org_same_pu, _ = create_organization_with_owner(
        user=u1,
        name="Allen Exact Spark",
        category=Organization.Category.ELECTRICIAN,
        phone="+2348010000001",
        polling_unit=pu_allen,
        callout_fee=Decimal("4000.00"),
        skills=["Solar Inverter", "Wiring"],
    )
    org_same_ward, _ = create_organization_with_owner(
        user=u2,
        name="Computer Village Power",
        category=Organization.Category.ELECTRICIAN,
        phone="+2348010000002",
        polling_unit=pu_comp_village,
        skills=["Panel Repair"],
    )
    org_covers_ward, _ = create_organization_with_owner(
        user=u3,
        name="Opebi Mobile Electric",
        category=Organization.Category.ELECTRICIAN,
        phone="+2348010000003",
        polling_unit=pu_opebi,
        service_wards=[pu_allen.ward],
    )
    org_same_lga, _ = create_organization_with_owner(
        user=u4,
        name="Alausa Busy Electric",
        category=Organization.Category.ELECTRICIAN,
        phone="+2348010000004",
        polling_unit=pu_alausa,
        availability_status=Organization.AvailabilityStatus.BUSY,
    )
    org_abuja, _ = create_organization_with_owner(
        user=u5,
        name="Abuja Solar Hub",
        category=Organization.Category.ELECTRICIAN,
        phone="+2348010000005",
        polling_unit=pu_wuse,
    )

    for org in [org_same_pu, org_same_ward, org_covers_ward, org_same_lga, org_abuja]:
        sf = get_or_create_storefront(org)
        sf.is_published = True
        sf.save()

    Product.objects.create(
        organization=org_same_pu,
        name="Emergency Fault Call-Out",
        slug="emergency-fault-call-out",
        product_type=Product.ProductType.SERVICE,
        price=Decimal("10000.00"),
        status=Product.Status.PUBLISHED,
        created_by=u1,
    )
    Product.objects.create(
        organization=org_same_ward,
        name="3kVA Inverter Unit",
        slug="3kva-inverter-unit",
        product_type=Product.ProductType.READY_MADE,
        price=Decimal("320000.00"),
        status=Product.Status.PUBLISHED,
        created_by=u2,
    )

    pub = APIClient()

    # Smart nearby search centered on Allen Polling Unit
    res = pub.get(
        reverse("marketplace-artisans"),
        {"polling_unit": str(pu_allen.id), "category": "electrician"},
    )
    assert res.status_code == 200
    names = [row["organization_name"] for row in res.data]
    tiers = [row["proximity_tier"] for row in res.data]

    assert names == [
        "Allen Exact Spark",
        "Computer Village Power",
        "Opebi Mobile Electric",
        "Alausa Busy Electric",
    ]
    assert tiers == ["same_polling_unit", "same_ward", "covers_ward", "same_lga"]
    assert "Abuja Solar Hub" not in names
    assert res.data[0]["distance_km"] == 0.0
    assert res.data[1]["distance_km"] is not None

    # Exact Polling Unit filter returns only artisans right at Allen PU
    exact_pu_res = pub.get(
        reverse("marketplace-artisans"),
        {"polling_unit": str(pu_allen.id), "category": "electrician", "exact": "true"},
    )
    assert exact_pu_res.status_code == 200
    assert [row["organization_name"] for row in exact_pu_res.data] == ["Allen Exact Spark"]

    # Exact Ward filter includes same ward + service_wards coverage
    exact_ward_res = pub.get(
        reverse("marketplace-artisans"),
        {"ward": str(pu_allen.ward_id), "category": "electrician", "exact": "true"},
    )
    assert exact_ward_res.status_code == 200
    assert set(row["organization_name"] for row in exact_ward_res.data) == {
        "Allen Exact Spark",
        "Computer Village Power",
        "Opebi Mobile Electric",
    }

    # Available-only filter excludes BUSY artisan
    avail_res = pub.get(
        reverse("marketplace-artisans"),
        {"polling_unit": str(pu_allen.id), "category": "electrician", "available_only": "true"},
    )
    assert avail_res.status_code == 200
    assert "Alausa Busy Electric" not in [row["organization_name"] for row in avail_res.data]

    # Marketplace products supports product_type=goods vs service + ward proximity
    goods_res = pub.get(
        reverse("marketplace-products"),
        {"polling_unit": str(pu_allen.id), "product_type": "goods"},
    )
    assert goods_res.status_code == 200
    assert [p["name"] for p in goods_res.data] == ["3kVA Inverter Unit"]
    assert goods_res.data[0]["proximity_tier"] == "same_ward"

    services_res = pub.get(
        reverse("marketplace-products"),
        {"polling_unit": str(pu_allen.id), "product_type": "service"},
    )
    assert services_res.status_code == 200
    assert [p["name"] for p in services_res.data] == ["Emergency Fault Call-Out"]
    assert services_res.data[0]["proximity_tier"] == "same_polling_unit"

    # Categories endpoint returns all trades with counts
    cats_res = pub.get(reverse("marketplace-categories"))
    assert cats_res.status_code == 200
    elec = next(c for c in cats_res.data if c["code"] == "electrician")
    assert elec["artisan_count"] == 5


@pytest.mark.django_db
def test_register_all_artisan_location_validation_work_callout_and_order_conversion():
    seed_nigeria_locations()
    pu_surulere = PollingUnit.objects.get(pu_code="LA/20/01/001")
    wrong_ward = NigerianWard.objects.exclude(id=pu_surulere.ward_id).first()

    pub = APIClient()

    # Mismatched polling unit + ward must be rejected
    bad_reg = pub.post(
        reverse("auth-register"),
        {
            "email": "badplumber@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Bad Plumber",
            "phone": "+2348090001122",
            "organization_name": "Mismatch Plumbing",
            "organization_category": "plumber",
            "nin": "34567890123",
            "ward": str(wrong_ward.id),
            "polling_unit": str(pu_surulere.id),
        },
        format="json",
    )
    assert bad_reg.status_code == 400

    # Valid registration with Polling Unit auto-fills State/LGA/Ward and publishes storefront
    reg = pub.post(
        reverse("auth-register"),
        {
            "email": "plumber@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Sodiq Plumber",
            "phone": "+2348090001123",
            "organization_name": "Surulere Rapid Pipes",
            "organization_category": "plumber",
            "nin": "45678901234",
            "cac_number": "BN2345678",
            "polling_unit": str(pu_surulere.id),
            "landmark": "Near Leisure Mall, Bode Thomas",
            "callout_fee": "3500.00",
            "skills": ["Leak Detection", "Pump Repair"],
        },
        format="json",
    )
    assert reg.status_code == 201
    org_data = reg.data["user"]["memberships"][0]["organization"]
    assert org_data["category"] == "plumber"
    assert org_data["polling_unit_code"] == "LA/20/01/001"
    assert org_data["ward_name"] == pu_surulere.ward.name
    assert org_data["state_name"] == "Lagos"

    slug = org_data["slug"]
    org_id = org_data["id"]

    # Approve artisan KYC so storefront becomes live for public call-outs
    admin_reviewer = User.objects.create_user(
        email="kyc-admin@test.ng",
        password="StrongPassword123!",
        full_name="Admin",
        is_platform_admin=True,
    )
    approve_artisan_kyc(organization=Organization.objects.get(id=org_id), reviewer=admin_reviewer)

    # Public customer submits an urgent work call-out pinned to their Polling Unit
    callout_res = pub.post(
        reverse("public-storefront-inquiry", args=[slug]),
        {
            "inquiry_type": StorefrontInquiry.InquiryType.WORK_CALLOUT,
            "urgency": StorefrontInquiry.Urgency.EMERGENCY,
            "buyer_name": "Chika Obi",
            "buyer_phone": "+2348087654321",
            "customer_polling_unit": str(pu_surulere.id),
            "customer_address": "18 Bode Thomas Street, Flat 3",
            "budget_amount": "15000.00",
            "message": "Kitchen sink pipe burst and flooding the floor, please come urgently.",
        },
        format="json",
    )
    assert callout_res.status_code == 201
    inquiry_id = callout_res.data["id"]
    assert callout_res.data["inquiry_type"] == "work_callout"
    assert callout_res.data["urgency"] == "emergency"
    assert callout_res.data["customer_polling_unit_code"] == "LA/20/01/001"

    # Artisan converts the work call-out directly into a tracked Customer + Order
    plumber_user = User.objects.get(email="plumber@test.ng")
    art_client = APIClient()
    art_client.force_authenticate(user=plumber_user)
    hdr = {"HTTP_X_ORGANIZATION_ID": org_id}

    convert_res = art_client.post(
        reverse("storefront-inquiry-convert", args=[inquiry_id]),
        {},
        format="json",
        **hdr,
    )
    assert convert_res.status_code == 201
    assert convert_res.data["customer_name"] == "Chika Obi"
    assert convert_res.data["quoted_amount"] == "15000.00"
    assert Customer.objects.filter(organization_id=org_id, phone="+2348087654321").exists()
    assert Order.objects.filter(organization_id=org_id, id=convert_res.data["id"]).exists()

    inquiry_obj = StorefrontInquiry.objects.get(id=inquiry_id)
    assert inquiry_obj.status == StorefrontInquiry.Status.CONVERTED
    assert str(inquiry_obj.converted_order_id) == convert_res.data["id"]

    # Double conversion rejected cleanly
    double_res = art_client.post(
        reverse("storefront-inquiry-convert", args=[inquiry_id]),
        {},
        format="json",
        **hdr,
    )
    assert double_res.status_code == 400


@pytest.mark.django_db
def test_auto_detect_gps_organic_ward_pu_mapping_and_customer_signup_spring_up():
    seed_nigeria_locations()
    pub = APIClient()

    # 1. GPS detect near Allen Roundabout matches existing Polling Unit immediately
    detect_known = pub.post(
        reverse("location-detect"),
        {"latitude": "6.601900", "longitude": "3.351500"},
        format="json",
    )
    assert detect_known.status_code == 200
    assert detect_known.data["match_source"] == "exact_nearby_pu"
    assert detect_known.data["polling_unit"]["pu_code"] == "LA/11/01/001"
    assert detect_known.data["state"]["code"] == "LA"

    # 2. Detect / map an unseeded LGA (Mushin, Lagos — one of the 774 LGAs!)
    mushin_lga = NigerianLGA.objects.get(state__code="LA", name="Mushin")
    detect_new = pub.post(
        reverse("location-detect"),
        {
            "latitude": "6.530000",
            "longitude": "3.350000",
            "state_name": "Lagos State",
            "lga_name": "Mushin",
            "ward_name": "Idi-Araba Ward",
            "polling_unit_name": "LUTH Main Gate Open Space",
        },
        format="json",
    )
    assert detect_new.status_code == 200
    assert detect_new.data["lga"]["id"] == str(mushin_lga.id)
    assert detect_new.data["ward"]["name"] == "Idi-Araba Ward"
    assert detect_new.data["polling_unit"]["name"] == "LUTH Main Gate Open Space"

    # 3. Artisan signs up in Mushin using custom ward_name & polling_unit_name (organic growth)
    art_reg = pub.post(
        reverse("auth-register"),
        {
            "email": "mushin.tailor@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Tope Tailor",
            "phone": "+2348055551234",
            "organization_name": "Idi-Araba Bespoke Stitches",
            "organization_category": "tailor",
            "nin": "56789012345",
            "lga": str(mushin_lga.id),
            "ward_name": "Idi-Araba Ward",
            "polling_unit_name": "LUTH Main Gate Open Space",
            "landmark": "Opposite LUTH Gate",
        },
        format="json",
    )
    assert art_reg.status_code == 201
    art_org = art_reg.data["user"]["memberships"][0]["organization"]
    assert art_org["ward_name"] == "Idi-Araba Ward"
    assert art_org["polling_unit_name"] == "LUTH Main Gate Open Space"
    admin_rev = User.objects.create_user(
        email="admin.mushin@test.ng",
        password="StrongPassword123!",
        full_name="Admin",
        is_platform_admin=True,
    )
    approve_artisan_kyc(organization=Organization.objects.get(id=art_org["id"]), reviewer=admin_rev)

    # 4. Customer signs up (no organization_name) with coordinates right at LUTH Gate
    #    -> User's Ward & PU are auto-detected, and the Mushin artisan springs up at #1!
    cust_reg = pub.post(
        reverse("auth-register"),
        {
            "email": "customer.mushin@test.ng",
            "password": "StrongPassword123!",
            "full_name": "Bola Customer",
            "phone": "+2348055559999",
            "latitude": "6.530100",
            "longitude": "3.350050",
        },
        format="json",
    )
    assert cust_reg.status_code == 201
    cust_user = cust_reg.data["user"]
    assert cust_user["memberships"] == []
    assert cust_user["ward_name"] == "Idi-Araba Ward"
    assert cust_user["polling_unit_name"] == "LUTH Main Gate Open Space"

    # Query nearby artisans using customer's auto-detected polling_unit -> Mushin tailor springs up #1!
    nearby_res = pub.get(
        reverse("marketplace-artisans"),
        {"polling_unit": cust_user["polling_unit"]},
    )
    assert nearby_res.status_code == 200
    assert len(nearby_res.data) >= 1
    assert nearby_res.data[0]["organization_name"] == "Idi-Araba Bespoke Stitches"
    assert nearby_res.data[0]["proximity_tier"] == "same_polling_unit"


@pytest.mark.django_db
def test_real_inec_csv_bulk_importer_and_coordinate_enrichment():
    import io
    from locations.inec_importer import import_inec_csv_stream

    # 1. Emeka-Onwuepe 176,846-row official INEC CSV format
    inec_csv = io.StringIO(
        "state,lg,ward,state_code,lg_code,ward_code,pu_code,code,Location\n"
        "ABIA,ABA NORTH,EZIAMA,01,01,01,001,01/01/01/001,ABIA STATE POLYTECHNIC GATE\n"
        "LAGOS,MUSHIN,ALAKARA,24,16,01,001,24/16/01/001,OPEN SPACE BY ALAKARA POLICE STATION\n"
        "FCT,MUNICIPAL AREA COUNCIL,WUSE,37,06,01,099,37/06/01/099,WUSE ZONE 4 OPEN SQUARE\n"
    )
    stats = import_inec_csv_stream(inec_csv)
    assert stats["polling_units_created"] == 3
    assert PollingUnit.objects.filter(pu_code="01/01/01/001", ward__lga__name="Aba North").exists()
    assert PollingUnit.objects.filter(pu_code="24/16/01/001", ward__lga__name="Mushin").exists()
    assert PollingUnit.objects.filter(pu_code="37/06/01/099", ward__lga__state__code="FC").exists()

    # 2. mykeels/inec-polling-units coordinate enrichment CSV format backfills GPS lat/lng
    geo_csv = io.StringIO(
        "state_name,local_government,ward_name,name,location.latitude,location.longitude\n"
        "Abia,Aba North,Eziama,Abia State Polytechnic Gate,5.121450,7.369810\n"
    )
    geo_stats = import_inec_csv_stream(geo_csv)
    assert geo_stats["coordinates_enriched"] == 1
    pu = PollingUnit.objects.get(pu_code="01/01/01/001")
    assert str(pu.latitude) == "5.121450"
    assert str(pu.longitude) == "7.369810"

    # 3. Stats endpoint returns real live database counts
    pub = APIClient()
    stats_res = pub.get(reverse("location-stats"))
    assert stats_res.status_code == 200
    assert stats_res.data["total_states"] == 37
    assert stats_res.data["total_lgas"] == 774
    assert stats_res.data["total_polling_units"] >= 3


