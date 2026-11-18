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
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.seed import seed_system_templates
from measurements.models import MeasurementProfile
from measurements.services import create_measurement_profile, revise_measurement_profile
from orders.models import Order
from orders.services import create_order, transition_order_status
from organizations.models import Membership, Organization
from organizations.services import create_organization_with_owner
from production.services import seed_standard_checklist


class Command(BaseCommand):
    help = "Idempotently seed realistic, clearly labeled demo data for local walkthroughs."

    @transaction.atomic
    def handle(self, *args, **options):
        seed_system_templates()
        plans = seed_default_plans()

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

        org = Organization.objects.filter(slug="savile-lagos-demo").first()
        if not org:
            org, _ = create_organization_with_owner(
                user=owner,
                name="Savile Lagos Bespoke (Demo)",
                category=Organization.Category.TAILOR,
                email="demo@artisanos.local",
                phone="+2348010000100",
                city="Lagos",
                country="Nigeria",
                currency="NGN",
                preferred_unit=Organization.UnitSystem.CM,
            )
            org.slug = "savile-lagos-demo"
            org.save(update_fields=["slug"])

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

        self.stdout.write(
            self.style.SUCCESS(
                "Demo data ready!\n"
                "  Owner login:   demo@artisanos.local / DemoArtisan2026! (Platform Admin)\n"
                "  Tailor login:  tailor@artisanos.local / DemoArtisan2026!\n"
                "  Public store:  /store/savile-lagos-demo"
            )
        )
