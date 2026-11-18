from decimal import Decimal

from django.db import transaction

from .models import Plan

DEFAULT_PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Essential workspace for solo tailors and independent artisans.",
        "monthly_price": Decimal("0.00"),
        "currency": "NGN",
        "max_members": 3,
        "max_customers": 50,
        "max_monthly_measurement_requests": 25,
        "max_products": 15,
        "display_order": 1,
    },
    {
        "code": "growth",
        "name": "Growth",
        "description": "For growing tailoring studios with a team, fittings calendar, and storefront.",
        "monthly_price": Decimal("15000.00"),
        "currency": "NGN",
        "max_members": 8,
        "max_customers": 500,
        "max_monthly_measurement_requests": 250,
        "max_products": 150,
        "display_order": 2,
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "High-volume fashion houses and multi-craft artisan businesses.",
        "monthly_price": Decimal("45000.00"),
        "currency": "NGN",
        "max_members": 25,
        "max_customers": 5000,
        "max_monthly_measurement_requests": 2000,
        "max_products": 1000,
        "display_order": 3,
    },
]


@transaction.atomic
def seed_default_plans() -> dict[str, Plan]:
    seeded: dict[str, Plan] = {}
    for spec in DEFAULT_PLANS:
        plan, _ = Plan.objects.get_or_create(code=spec["code"], defaults=spec)
        seeded[spec["code"]] = plan
    return seeded
