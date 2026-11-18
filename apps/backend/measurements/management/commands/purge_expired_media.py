from django.core.management.base import BaseCommand

from measurements.media_services import purge_expired_media_assets


class Command(BaseCommand):
    help = "Physically delete expired customer reference photos past their retention window."

    def handle(self, *args, **options):
        purged = purge_expired_media_assets()
        self.stdout.write(self.style.SUCCESS(f"Purged {purged} expired media asset(s)."))
