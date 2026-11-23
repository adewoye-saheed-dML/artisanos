from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from billing.seed import seed_default_plans
from billing.services import get_or_create_subscription
from catalog.models import Product, Storefront
from catalog.services import create_product_with_initial_stock, get_or_create_storefront
from customers.models import Customer
from locations.models import NigerianWard, PollingUnit
from locations.seed import seed_nigeria_locations
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.models import MeasurementProfile
from measurements.services import create_measurement_profile, revise_measurement_profile
from orders.models import Order
from orders.services import create_order, transition_order_status
from organizations.kyc_services import approve_artisan_kyc, submit_artisan_kyc
from organizations.models import ArtisanVerification, Membership, Organization
from organizations.services import create_organization_with_owner
from production.services import seed_standard_checklist


class Command(BaseCommand):
    help = "Idempotently seed realistic, clearly labeled demo data for local walkthroughs."

    @transaction.atomic
    def handle(self, *args, **options):
        seed_system_templates()
        plans = seed_default_plans()
        seed_nigeria_locations()

        owner, _ = User.objects.get_or_create(
            email="demo@artisanos.local",
            defaults={
                "full_name": "Adaobi Nwosu (Demo Owner)",
                "phone": "+2348010000100",
                "is_platform_admin": True,
            },
        )
        owner.set_password("DemoArtisan2026!")
        owner.is_platform_admin = True
        owner.save()

        artisan, _ = User.objects.get_or_create(
            email="tailor@artisanos.local",
            defaults={
                "full_name": "Chinedu Okafor (Demo Tailor)",
                "phone": "+2348010000101",
            },
        )
        artisan.set_password("DemoArtisan2026!")
        artisan.save()

        vi_pu = PollingUnit.objects.filter(pu_code="LA/08/01/001").select_related("ward", "ward__lga", "ward__lga__state").first()
        lekki_ward = NigerianWard.objects.filter(name__icontains="Lekki").first()

        org = Organization.objects.filter(slug="savile-lagos-demo").first()
        if not org:
            org, _ = create_organization_with_owner(
                user=owner,
                name="Savile Lagos Bespoke (Demo)",
                category=Organization.Category.TAILOR,
                email="demo@artisanos.local",
                phone="+2348010000100",
                city="Eti-Osa",
                country="Nigeria",
                polling_unit=vi_pu,
                landmark="Plot 14 Adeola Odeku Street, Victoria Island",
                available_for_callout=True,
                callout_fee=Decimal("5000.00"),
                years_experience=9,
                skills=["Agbada", "Bespoke Suits", "Bridal Occasionwear", "Home Measurement Visit"],
                currency="NGN",
                preferred_unit=Organization.UnitSystem.CM,
            )
            org.slug = "savile-lagos-demo"
            org.is_verified = True
            org.verification_status = Organization.VerificationStatus.APPROVED
            org.save(update_fields=["slug", "is_verified", "verification_status"])
            if lekki_ward:
                org.service_wards.add(lekki_ward)
        if not ArtisanVerification.objects.filter(organization=org).exists():
            submit_artisan_kyc(
                organization=org,
                submitted_by=owner,
                nin="12345678901",
                cac_number="RC1849201",
                cac_business_name="Savile Lagos Bespoke Ltd",
                guarantor_name="Chief Femi Adewale",
                guarantor_phone="+2348010000199",
                bank_name="GTBank",
                bank_account_number="0123456789",
                bank_account_name="Savile Lagos Bespoke Ltd",
            )
            approve_artisan_kyc(organization=org, reviewer=owner, notes="Seeded verified demo artisan.")
        elif vi_pu and not org.polling_unit_id:
            org.state = vi_pu.ward.lga.state
            org.lga = vi_pu.ward.lga
            org.ward = vi_pu.ward
            org.polling_unit = vi_pu
            org.landmark = "Plot 14 Adeola Odeku Street, Victoria Island"
            org.callout_fee = Decimal("5000.00")
            org.years_experience = 9
            org.skills = ["Agbada", "Bespoke Suits", "Bridal Occasionwear", "Home Measurement Visit"]
            org.is_verified = True
            org.save()
            if lekki_ward:
                org.service_wards.add(lekki_ward)

        Membership.objects.get_or_create(
            user=artisan,
            organization=org,
            defaults={"role": Membership.Role.ARTISAN, "status": Membership.Status.ACTIVE},
        )

        sub = get_or_create_subscription(org)
        sub.plan = plans["growth"]
        sub.save(update_fields=["plan", "updated_at"])

        sf = get_or_create_storefront(org)
        sf.headline = "Hand-finished bespoke tailoring & contemporary occasionwear (Demo)"
        sf.bio = "Demo workshop showcasing ArtisanOS measurement history, orders, and storefront."
        sf.whatsapp_number = "+2348010000100"
        sf.instagram_handle = "@savilelagosdemo"
        sf.is_published = True
        sf.save()

        tailoring_v1 = MeasurementTemplateVersion.objects.get(
            template__slug="standard-tailoring",
            version_number=1,
        )

        demo_customers_spec = [
            ("Tunde Balogun (Demo)", "+2348021112201", "tunde.demo@example.com", "whatsapp"),
            ("Ngozi Eze (Demo)", "+2348021112202", "ngozi.demo@example.com", "phone"),
            ("Yusuf Abdullahi (Demo)", "+2348021112203", "yusuf.demo@example.com", "whatsapp"),
        ]
        customers = []
        for full_name, phone, email, contact in demo_customers_spec:
            cust, _ = Customer.objects.get_or_create(
                organization=org,
                phone=phone,
                defaults={
                    "full_name": full_name,
                    "email": email,
                    "preferred_contact_method": contact,
                    "notes": "Demo customer record.",
                    "created_by": owner,
                },
            )
            customers.append(cust)

        # Create versioned measurements for first customer if none exist
        if not MeasurementProfile.objects.filter(organization=org, customer=customers[0]).exists():
            v1 = create_measurement_profile(
                organization=org,
                customer=customers[0],
                template_version=tailoring_v1,
                label="Ceremonial Agbada Fit",
                unit_system="cm",
                status="verified",
                values_payload=[
                    {"field_key": "neck", "numeric_value": "41.0"},
                    {"field_key": "chest", "numeric_value": "106.0"},
                    {"field_key": "waist", "numeric_value": "90.0"},
                    {"field_key": "hip", "numeric_value": "104.0"},
                    {"field_key": "shoulder_width", "numeric_value": "47.0"},
                    {"field_key": "sleeve_length", "numeric_value": "64.0"},
                ],
                created_by=owner,
            )
            v2 = revise_measurement_profile(
                profile=v1,
                actor=owner,
                notes="Updated waist and chest after second fitting.",
                values_payload=[
                    {"field_key": "neck", "numeric_value": "41.0"},
                    {"field_key": "chest", "numeric_value": "107.5"},
                    {"field_key": "waist", "numeric_value": "91.0"},
                    {"field_key": "hip", "numeric_value": "104.0"},
                    {"field_key": "shoulder_width", "numeric_value": "47.0"},
                    {"field_key": "sleeve_length", "numeric_value": "64.5"},
                ],
            )
        else:
            v2 = MeasurementProfile.objects.filter(organization=org, customer=customers[0], is_latest=True).first()

        # Seed demo orders if none exist
        if not Order.objects.filter(organization=org).exists():
            o1 = create_order(
                organization=org,
                created_by=owner,
                validated_data={
                    "customer": customers[0],
                    "garment_type": "Three-Piece Embroidered Agbada",
                    "measurement_profile": v2,
                    "status": Order.Status.QUOTED,
                    "quoted_amount": Decimal("185000.00"),
                    "deposit_amount": Decimal("100000.00"),
                    "assigned_to": artisan,
                    "expected_completion_date": (timezone.now() + timedelta(days=7)).date(),
                    "category_options": {"fabric_source": "Studio Italian Cashmere", "lining": "Half-lined silk"},
                },
            )
            transition_order_status(order=o1, to_status=Order.Status.CONFIRMED, actor=owner, notes="Deposit cleared")
            transition_order_status(order=o1, to_status=Order.Status.IN_PRODUCTION, actor=artisan, notes="Cutting started")
            seed_standard_checklist(organization=org, order=o1, actor=owner)

            o2 = create_order(
                organization=org,
                created_by=owner,
                validated_data={
                    "customer": customers[1],
                    "garment_type": "Structured Velvet Dinner Suit",
                    "status": Order.Status.CONFIRMED,
                    "quoted_amount": Decimal("240000.00"),
                    "deposit_amount": Decimal("120000.00"),
                    "assigned_to": artisan,
                    "expected_completion_date": (timezone.now() + timedelta(days=10)).date(),
                },
            )
            seed_standard_checklist(organization=org, order=o2, actor=owner)

            Appointment.objects.create(
                organization=org,
                customer=customers[0],
                order=o1,
                appointment_type=Appointment.AppointmentType.FIRST_FITTING,
                title="First Agbada Fitting (Demo)",
                scheduled_at=timezone.now() + timedelta(days=2),
                duration_minutes=45,
                location="Victoria Island Studio",
                assigned_to=artisan,
                created_by=owner,
            )

        # Seed demo storefront products if none exist
        if not Product.objects.filter(organization=org).exists():
            create_product_with_initial_stock(
                organization=org,
                created_by=owner,
                validated_data={
                    "name": "Lagos Linen Resort Shirt (Demo)",
                    "category": "Ready-to-Wear",
                    "product_type": Product.ProductType.READY_MADE,
                    "price": Decimal("48000.00"),
                    "status": Product.Status.PUBLISHED,
                    "track_inventory": True,
                    "initial_stock": 8,
                    "description": "Breathable stone-washed linen shirt ready for studio pickup.",
                },
            )
            create_product_with_initial_stock(
                organization=org,
                created_by=owner,
                validated_data={
                    "name": "Bespoke Two-Piece Suit Commission (Demo)",
                    "category": "Bespoke Tailoring",
                    "product_type": Product.ProductType.MADE_TO_ORDER,
                    "price": Decimal("220000.00"),
                    "status": Product.Status.PUBLISHED,
                    "track_inventory": False,
                    "description": "Includes consultation, full 16-point measurement profile, and two fittings.",
                },
            )

        # Seed multi-trade Nigerian demo artisans across Wards & Polling Units
        extra_artisans = [
            {
                "slug": "voltcraft-ikeja-demo",
                "email": "electrician@artisanos.local",
                "owner_name": "Emeka Nwankwo (Demo Electrician)",
                "phone": "+2348035550101",
                "org_name": "VoltCraft Solar & Electricals (Demo)",
                "category": Organization.Category.ELECTRICIAN,
                "pu_code": "LA/11/01/001",
                "extra_ward": "Opebi / Allen",
                "landmark": "Beside Allen Roundabout Plaza, Ikeja",
                "callout_fee": Decimal("4000.00"),
                "years_experience": 11,
                "skills": ["House Wiring", "Solar Inverter Setup", "DB Panel Repair", "Prepaid Meter Faults"],
                "headline": "24/7 licensed electrician & solar inverter specialist in Ikeja & Opebi",
                "bio": "Fast fault diagnosis, neat conduit wiring, and lithium solar installations across Ikeja wards.",
                "listings": [
                    (
                        "Emergency Electrical Fault Diagnosis & Call-Out",
                        "Electrical Service",
                        Product.ProductType.SERVICE,
                        Decimal("12000.00"),
                        False,
                        0,
                        "On-site troubleshooting for tripping breakers, sockets, and changeover switches.",
                    ),
                    (
                        "3.5kVA Hybrid Solar Inverter Installation Package",
                        "Solar & Power",
                        Product.ProductType.READY_MADE,
                        Decimal("680000.00"),
                        True,
                        4,
                        "Includes inverter, tubular battery bank setup, surge protection, and 1-year warranty.",
                    ),
                ],
            },
            {
                "slug": "surulere-aqua-plumbing-demo",
                "email": "plumber@artisanos.local",
                "owner_name": "Sodiq Adeyemi (Demo Plumber)",
                "phone": "+2348035550102",
                "org_name": "AquaFlow Plumbing & Borehole Works (Demo)",
                "category": Organization.Category.PLUMBER,
                "pu_code": "LA/20/01/001",
                "extra_ward": "Aguda / Ijesha",
                "landmark": "Near Bode Thomas / Leisure Mall, Surulere",
                "callout_fee": Decimal("3500.00"),
                "years_experience": 8,
                "skills": ["Leak Detection", "WC & Mixer Installation", "Pumping Machine Repair", "Overhead Tank Piping"],
                "headline": "Same-day plumbing repairs, bathroom fittings & borehole pumps in Surulere",
                "bio": "Clean leak fixes, concealed shower installations, and water pump maintenance around Bode Thomas.",
                "listings": [
                    (
                        "Same-Day Pipe Leak & Drainage Fix",
                        "Plumbing Repair",
                        Product.ProductType.SERVICE,
                        Decimal("10000.00"),
                        False,
                        0,
                        "Quick kitchen sink, toilet cistern, or burst pipe repair in Surulere & environs.",
                    ),
                    (
                        "Chrome Concealed Rain Shower Mixer Set",
                        "Sanitary Hardware",
                        Product.ProductType.READY_MADE,
                        Decimal("65000.00"),
                        True,
                        6,
                        "Solid brass anti-rust shower set with free installation within Bode Thomas ward.",
                    ),
                ],
            },
            {
                "slug": "yaba-craft-shoemakers-demo",
                "email": "shoemaker@artisanos.local",
                "owner_name": "Kelechi Osuji (Demo Shoemaker)",
                "phone": "+2348035550103",
                "org_name": "Yaba Heritage Leather & Footwear (Demo)",
                "category": Organization.Category.SHOEMAKER,
                "pu_code": "LA/15/01/001",
                "extra_ward": "Ebute Metta",
                "landmark": "Opposite YabaTech Front Gate, Herbert Macaulay Way",
                "callout_fee": Decimal("2500.00"),
                "years_experience": 7,
                "skills": ["Handcrafted Loafers", "Leather Palm Sandals", "Sole Replacement", "Custom Sizing"],
                "headline": "Handcrafted full-grain Nigerian leather loafers, palms & shoe restoration",
                "bio": "Bespoke and ready-to-wear footwear handcrafted in Yaba with nationwide delivery.",
                "listings": [
                    (
                        "Handstitched Full-Grain Leather Palm Slippers",
                        "Ready-to-Wear Footwear",
                        Product.ProductType.READY_MADE,
                        Decimal("28000.00"),
                        True,
                        12,
                        "Cushioned vegetable-tanned leather palms in sizes 40–46.",
                    ),
                    (
                        "Bespoke Goodyear-Welted Oxford Shoes",
                        "Bespoke Footwear",
                        Product.ProductType.MADE_TO_ORDER,
                        Decimal("75000.00"),
                        False,
                        0,
                        "Custom-lasted calfskin shoes measured to your exact foot profile.",
                    ),
                ],
            },
            {
                "slug": "lekki-timber-carpentry-demo",
                "email": "carpenter@artisanos.local",
                "owner_name": "Babatunde Lawal (Demo Carpenter)",
                "phone": "+2348035550104",
                "org_name": "Oakline Carpentry & Kitchens (Demo)",
                "category": Organization.Category.CARPENTER,
                "pu_code": "LA/08/02/001",
                "extra_ward": "Victoria Island I",
                "landmark": "Off Admiralty Way, Lekki Phase 1",
                "callout_fee": Decimal("5000.00"),
                "years_experience": 10,
                "skills": ["Kitchen Cabinets", "Wardrobes", "Door Hanging & Locks", "TV Consoles"],
                "headline": "Modern wardrobes, HDF/marine-board kitchens & home carpentry in Lekki & VI",
                "bio": "Precision furniture fabrication and fast on-site door, hinge, and cabinet repairs.",
                "listings": [
                    (
                        "Floating Minimalist TV Console (6ft)",
                        "Custom Furniture",
                        Product.ProductType.MADE_TO_ORDER,
                        Decimal("165000.00"),
                        False,
                        0,
                        "High-gloss finish with hidden cable channels; delivered & mounted in 5 days.",
                    ),
                    (
                        "Door Lock, Hinge & Cabinet Repair Visit",
                        "Carpentry Service",
                        Product.ProductType.SERVICE,
                        Decimal("15000.00"),
                        False,
                        0,
                        "On-site repair for sagging doors, broken locks, and wardrobe rails.",
                    ),
                ],
            },
            {
                "slug": "wuse-autocare-mechanic-demo",
                "email": "mechanic@artisanos.local",
                "owner_name": "Ibrahim Musa (Demo Mechanic)",
                "phone": "+2348035550105",
                "org_name": "Wuse AutoCare & OBD Diagnostics (Demo)",
                "category": Organization.Category.MECHANIC,
                "pu_code": "FC/06/01/002",
                "extra_ward": "Maitama",
                "landmark": "Behind Banex Plaza, Aminu Kano Crescent, Wuse II",
                "callout_fee": Decimal("5000.00"),
                "years_experience": 12,
                "skills": ["Toyota & Lexus Specialist", "OBD2 Scanning", "Roadside Rescue", "AC Gas Refill"],
                "headline": "Mobile auto diagnostics, brake service & roadside mechanic in Wuse II & Maitama",
                "bio": "Computerized fault scanning and transparent repairs at your home, office, or our Wuse II bay.",
                "listings": [
                    (
                        "Mobile OBD2 Diagnostics & Home Car Service",
                        "Auto Service",
                        Product.ProductType.SERVICE,
                        Decimal("18000.00"),
                        False,
                        0,
                        "Full engine scan, oil/filter service, and brake pad check right at your location.",
                    ),
                ],
            },
        ]

        for spec in extra_artisans:
            art_user, _ = User.objects.get_or_create(
                email=spec["email"],
                defaults={
                    "full_name": spec["owner_name"],
                    "phone": spec["phone"],
                },
            )
            art_user.set_password("DemoArtisan2026!")
            art_user.save()

            art_org = Organization.objects.filter(slug=spec["slug"]).first()
            if not art_org:
                pu = PollingUnit.objects.filter(pu_code=spec["pu_code"]).select_related("ward", "ward__lga", "ward__lga__state").first()
                art_org, _ = create_organization_with_owner(
                    user=art_user,
                    name=spec["org_name"],
                    category=spec["category"],
                    email=spec["email"],
                    phone=spec["phone"],
                    polling_unit=pu,
                    landmark=spec["landmark"],
                    available_for_callout=True,
                    callout_fee=spec["callout_fee"],
                    years_experience=spec["years_experience"],
                    skills=spec["skills"],
                    currency="NGN",
                )
                art_org.slug = spec["slug"]
                art_org.is_verified = True
                art_org.verification_status = Organization.VerificationStatus.APPROVED
                art_org.save(update_fields=["slug", "is_verified", "verification_status"])
                extra_ward = NigerianWard.objects.filter(name__icontains=spec["extra_ward"]).first()
                if extra_ward:
                    art_org.service_wards.add(extra_ward)

            if not ArtisanVerification.objects.filter(organization=art_org).exists():
                submit_artisan_kyc(
                    organization=art_org,
                    submitted_by=art_user,
                    nin=f"2345678{abs(hash(spec['slug'])) % 10000:04d}",
                    cac_number=f"BN{2000000 + abs(hash(spec['slug'])) % 899999}",
                    cac_business_name=spec["org_name"],
                    guarantor_name="Verified Community Guarantor",
                    guarantor_phone="+2348099990000",
                    bank_name="Access Bank",
                    bank_account_number="0011223344",
                    bank_account_name=spec["org_name"],
                )
                approve_artisan_kyc(organization=art_org, reviewer=owner, notes="Seeded verified demo artisan.")

            art_sf = get_or_create_storefront(art_org)
            art_sf.headline = spec["headline"]
            art_sf.bio = spec["bio"]
            art_sf.whatsapp_number = spec["phone"]
            art_sf.is_published = True
            art_sf.save()

            if not Product.objects.filter(organization=art_org).exists():
                for pname, pcat, ptype, pprice, track, stock, pdesc in spec["listings"]:
                    create_product_with_initial_stock(
                        organization=art_org,
                        created_by=art_user,
                        validated_data={
                            "name": pname,
                            "category": pcat,
                            "product_type": ptype,
                            "price": pprice,
                            "status": Product.Status.PUBLISHED,
                            "track_inventory": track,
                            "initial_stock": stock,
                            "description": pdesc,
                        },
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready!\n"
                "  Owner login:   demo@artisanos.local / DemoArtisan2026! (Platform Admin)\n"
                "  Tailor login:  tailor@artisanos.local / DemoArtisan2026!\n"
                "  Public store:  /store/savile-lagos-demo\n"
                "  Marketplace:   /marketplace (Multi-trade Nigerian Wards & Polling Units seeded)"
            )
        )
