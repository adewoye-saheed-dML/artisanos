import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import User
from billing.seed import seed_default_plans
from locations.models import NigerianLGA, NigerianState, PollingUnit
from locations.seed import seed_nigeria_locations
from measurement_templates.seed import seed_system_templates
from organizations.models import Organization


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = (
        "Idempotent zero-shell deploy bootstrap for Render Free and paid tiers: "
        "seeds system templates, billing plans, Nigeria states/774 LGAs/wards/polling units, "
        "optional env-configured Platform Admin superuser, and optional demo data."
    )

    def handle(self, *args, **options):
        # 1. Measurement templates & subscription plans (fast, idempotent)
        seed_system_templates()
        seed_default_plans()
        self.stdout.write(self.style.SUCCESS("Templates and billing plans ready."))

        # 2. Nigerian baseline locations (37 states, 774 LGAs, baseline wards & PUs)
        # Fast-path skip when already seeded so Render Free cold starts stay instant.
        if (
            NigerianState.objects.count() >= 37
            and NigerianLGA.objects.count() >= 774
            and PollingUnit.objects.count() >= 50
        ):
            self.stdout.write(
                f"Nigeria locations already seeded ({NigerianState.objects.count()} states, "
                f"{NigerianLGA.objects.count()} LGAs, {PollingUnit.objects.count()} polling units)."
            )
        else:
            stats = seed_nigeria_locations()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded Nigeria locations: {stats['total_states']} states, "
                    f"{stats['total_lgas']} LGAs, {stats['total_wards']} wards, "
                    f"{stats['total_polling_units']} polling units."
                )
            )

        # 3. Optional env-var Platform Admin / Superuser bootstrap (no Shell required)
        admin_email = (os.getenv("DJANGO_SUPERUSER_EMAIL") or "").strip().lower()
        admin_password = os.getenv("DJANGO_SUPERUSER_PASSWORD") or ""
        admin_name = (os.getenv("DJANGO_SUPERUSER_FULL_NAME") or "Platform Admin").strip()
        reset_password = _env_bool("DJANGO_SUPERUSER_RESET_PASSWORD", False)

        if admin_email and admin_password:
            existing = User.objects.filter(email__iexact=admin_email).first()
            if existing is None:
                User.objects.create_superuser(
                    email=admin_email,
                    password=admin_password,
                    full_name=admin_name or "Platform Admin",
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created Platform Admin superuser: {admin_email}")
                )
            else:
                changed = False
                if not existing.is_staff:
                    existing.is_staff = True
                    changed = True
                if not existing.is_superuser:
                    existing.is_superuser = True
                    changed = True
                if not existing.is_platform_admin:
                    existing.is_platform_admin = True
                    changed = True
                if not existing.is_active:
                    existing.is_active = True
                    changed = True
                if reset_password:
                    existing.set_password(admin_password)
                    changed = True
                if changed:
                    existing.save()
                    self.stdout.write(
                        self.style.SUCCESS(f"Updated Platform Admin superuser: {admin_email}")
                    )
                else:
                    self.stdout.write(f"Platform Admin superuser already ready: {admin_email}")
        elif admin_email or admin_password:
            self.stdout.write(
                self.style.WARNING(
                    "Skipping superuser bootstrap: set both DJANGO_SUPERUSER_EMAIL and "
                    "DJANGO_SUPERUSER_PASSWORD."
                )
            )

        # 4. Optional demo data seed (e.g. SEED_DEMO_DATA=True on staging)
        if _env_bool("SEED_DEMO_DATA", False):
            if Organization.objects.filter(slug="savile-lagos-demo").exists():
                self.stdout.write("Demo data already seeded; skipping.")
            else:
                call_command("seed_demo_data", stdout=self.stdout)
