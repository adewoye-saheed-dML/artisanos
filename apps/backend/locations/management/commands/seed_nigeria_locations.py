from django.core.management.base import BaseCommand

from locations.inec_importer import sync_full_inec_dataset
from locations.seed import import_locations_from_json, seed_nigeria_locations


class Command(BaseCommand):
    help = "Idempotently seed all 37 Nigerian States and 774 LGAs, or sync all 176,846 INEC Polling Units with --full-inec."

    def add_arguments(self, parser):
        parser.add_argument(
            "--full-inec",
            action="store_true",
            default=False,
            help="Download and import ALL ~176,846 real INEC Polling Units and 8,809 Wards from open INEC datasets.",
        )
        parser.add_argument(
            "--from-csv",
            dest="from_csv",
            default="",
            help="Optional local path to an INEC CSV dataset (e.g. Nigeria_polling_units.csv).",
        )
        parser.add_argument(
            "--from-json",
            dest="from_json",
            default="",
            help="Optional path to an INEC JSON dataset of Nigerian wards and polling units to bulk import.",
        )

    def handle(self, *args, **options):
        stats = seed_nigeria_locations()
        self.stdout.write(
            self.style.SUCCESS(
                f"Base Nigeria locations ready: {stats['total_states']} states, "
                f"{stats['total_lgas']} LGAs, {stats['total_wards']} wards, "
                f"{stats['total_polling_units']} polling units."
            )
        )
        if options.get("full_inec") or options.get("from_csv"):
            inec_stats = sync_full_inec_dataset(
                csv_path=options.get("from_csv") or None,
                progress_callback=lambda msg: self.stdout.write(msg),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Full INEC dataset synced: {inec_stats['total_states']} states, "
                    f"{inec_stats['total_lgas']} LGAs, {inec_stats['total_wards']} wards, "
                    f"{inec_stats['total_polling_units']} polling units "
                    f"({inec_stats['geolocated_polling_units']} geolocated)."
                )
            )
        json_path = options.get("from_json")
        if json_path:
            imported = import_locations_from_json(json_path)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {imported['polling_units_imported']} additional polling units from {json_path}."
                )
            )
