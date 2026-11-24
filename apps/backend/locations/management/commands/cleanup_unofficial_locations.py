from django.core.management.base import BaseCommand

from locations.services import cleanup_unofficial_locations


class Command(BaseCommand):
    help = (
        "Inspect or remove legacy auto-generated /AUTO/ Polling Units and orphaned non-official Wards "
        "(e.g. OSM town names created before GRID3 Ward Boundary standardization) that are unreferenced."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Actually delete unreferenced legacy /AUTO/ records (default is dry-run).",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply", False))
        report = cleanup_unofficial_locations(dry_run=not apply_changes)
        mode = "APPLIED" if apply_changes else "DRY RUN (pass --apply to delete)"
        self.stdout.write(
            self.style.SUCCESS(
                f"Unofficial location cleanup [{mode}]:\n"
                f"  Legacy /AUTO/ Polling Units removable: {report['legacy_auto_pus_removed']}\n"
                f"  Legacy /AUTO/ Polling Units in use:    {report['legacy_auto_pus_protected']}\n"
                f"  Orphaned legacy Wards removable:       {report['orphaned_wards_removed']}"
            )
        )
