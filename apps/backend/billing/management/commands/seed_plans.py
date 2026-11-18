from django.core.management.base import BaseCommand

from billing.seed import seed_default_plans


class Command(BaseCommand):
    help = "Seed default ArtisanOS SaaS subscription plans (Starter, Growth, Professional)."

    def handle(self, *args, **options):
        plans = seed_default_plans()
        for code, plan in plans.items():
            self.stdout.write(self.style.SUCCESS(f"Ensured plan '{plan.name}' ({code})"))
