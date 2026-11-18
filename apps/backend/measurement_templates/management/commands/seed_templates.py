from django.core.management.base import BaseCommand

from measurement_templates.seed import seed_system_templates


class Command(BaseCommand):
    help = "Seed built-in system measurement templates (tailoring and shoemaking)."

    def handle(self, *args, **options):
        seeded = seed_system_templates()
        for slug, template in seeded.items():
            self.stdout.write(self.style.SUCCESS(f"Ensured template '{template.name}' ({slug})"))
