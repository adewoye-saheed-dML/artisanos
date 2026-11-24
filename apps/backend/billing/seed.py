from decimal import Decimal

from django.db import transaction

from .models import Plan

DEFAULT_PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Free essentials for solo artisans getting listed in their primary neighborhood.",
        "monthly_price": Decimal("0.00"),
        "annual_price": Decimal("0.00"),
        "currency": "NGN",
        "max_members": 3,
        "max_customers": 50,
        "max_monthly_measurement_requests": 25,
        "max_products": 15,
        "max_service_wards": 1,
        "escrow_fee_rate_pct": Decimal("3.00"),
        "monthly_free_boosts": 0,
        "is_popular": False,
        "display_order": 1,
    },
    {
        "code": "solo_pro",
        "name": "Solo Pro",
        "description": "Built for busy independent tradespeople covering up to 5 nearby neighborhoods with lower escrow fees.",
        "monthly_price": Decimal("3500.00"),
        "annual_price": Decimal("35000.00"),
        "currency": "NGN",
        "max_members": 4,
        "max_customers": 150,
        "max_monthly_measurement_requests": 80,
        "max_products": 50,
        "max_service_wards": 5,
        "escrow_fee_rate_pct": Decimal("2.50"),
        "monthly_free_boosts": 0,
        "is_popular": True,
        "display_order": 2,
    },
    {
        "code": "growth",
        "name": "Workshop Growth",
        "description": "For growing workshops with a team, wide LGA coverage, 1 monthly spotlight boost, and 2% escrow fees.",
        "monthly_price": Decimal("15000.00"),
        "annual_price": Decimal("150000.00"),
        "currency": "NGN",
        "max_members": 8,
        "max_customers": 500,
        "max_monthly_measurement_requests": 250,
        "max_products": 150,
        "max_service_wards": 20,
        "escrow_fee_rate_pct": Decimal("2.00"),
        "monthly_free_boosts": 1,
        "is_popular": False,
        "display_order": 3,
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "High-volume fashion houses, contractors, and multi-craft teams with 3 monthly boosts and 1.5% escrow fees.",
        "monthly_price": Decimal("45000.00"),
        "annual_price": Decimal("450000.00"),
        "currency": "NGN",
        "max_members": 25,
        "max_customers": 5000,
        "max_monthly_measurement_requests": 2000,
        "max_products": 1000,
        "max_service_wards": 100,
        "escrow_fee_rate_pct": Decimal("1.50"),
        "monthly_free_boosts": 3,
        "is_popular": False,
        "display_order": 4,
    },
]


@transaction.atomic
def seed_default_plans() -> dict[str, Plan]:
    """Idempotently seed all 4 Nigeria-calibrated SaaS plans and sync Phase 1 entitlement metadata."""
    seeded: dict[str, Plan] = {}
    for spec in DEFAULT_PLANS:
        plan, created = Plan.objects.get_or_create(code=spec["code"], defaults=spec)
        if not created:
            update_fields: list[str] = []
            for field in (
                "annual_price",
                "max_service_wards",
                "escrow_fee_rate_pct",
                "monthly_free_boosts",
                "is_popular",
                "display_order",
                "description",
                "name",
            ):
                target = spec[field]
                if getattr(plan, field) != target:
                    setattr(plan, field, target)
                    update_fields.append(field)
            if update_fields:
                update_fields.append("updated_at")
                plan.save(update_fields=update_fields)
        seeded[spec["code"]] = plan
    return seeded
