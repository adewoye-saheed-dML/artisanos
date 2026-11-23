from django.core.management.base import BaseCommand

from locations.inec_importer import sync_full_inec_dataset


class Command(BaseCommand):
    help = (
        "Download and bulk-import ALL ~176,846 real Nigerian INEC Polling Units, "
        "8,809 Wards, 774 LGAs, and 37 States (plus GPS coordinates) into PostgreSQL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-csv",
            dest="from_csv",
            default="",
            help="Optional local path to an INEC Polling Units CSV file (e.g. Nigeria_polling_units.csv).",
        )
        parser.add_argument(
            "--url",
            dest="url",
            default="",
            help="Optional custom raw CSV URL for INEC polling units.",
        )
        parser.add_argument(
            "--skip-geo",
            action="store_true",
            default=False,
            help="Skip downloading the secondary GPS coordinates enrichment CSV.",
        )

    def handle(self, *args, **options):
        stats = sync_full_inec_dataset(
            csv_path=options.get("from_csv") or None,
            custom_url=options.get("url") or None,
            include_geo_enrichment=not options.get("skip_geo", False),
            progress_callback=lambda msg: self.stdout.write(msg),
        )
        self.stdout.write(
            self.style.SUCCESS(
                "INEC Sync Complete!\n"
                f"  States:            {stats['total_states']}\n"
                f"  LGAs:              {stats['total_lgas']}\n"
                f"  Wards:             {stats['total_wards']}\n"
                f"  Polling Units:     {stats['total_polling_units']}\n"
                f"  Geolocated PUs:    {stats['geolocated_polling_units']}\n"
                f"  New PUs imported:  {stats['polling_units_created']}\n"
                f"  Coords enriched:   {stats['coordinates_enriched']}"
            )
        )
