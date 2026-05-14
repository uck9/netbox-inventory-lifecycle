import logging
import sys

from django.core.management.base import BaseCommand

from netbox_inventory.jobs.sync_cisco_hw_eox import SyncCiscoHwEoXDates


class _FakeJob:
    """Minimal stub satisfying JobRunner's job interface for CLI use."""

    error = None

    def start(self):
        pass

    def terminate(self, status=None, error=None):
        if error:
            print(f"Job terminated with error: {error}", file=sys.stderr)

    def log(self, record):
        pass


class Command(BaseCommand):
    help = "Run the Cisco HW EoX sync job immediately (same logic as the scheduled job)"

    def handle(self, *args, **options):
        verbosity = options.get("verbosity", 1)
        if verbosity >= 2:
            log_level = logging.DEBUG
        elif verbosity >= 1:
            log_level = logging.INFO
        else:
            log_level = logging.WARNING

        logger = logging.getLogger(f"netbox.jobs.{SyncCiscoHwEoXDates.__name__}")
        handler = logging.StreamHandler(self.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(log_level)

        self.stdout.write("Starting Cisco HW EoX sync...")
        try:
            SyncCiscoHwEoXDates(_FakeJob()).run()
            self.stdout.write(self.style.SUCCESS("Cisco HW EoX sync completed."))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Sync failed: {exc}"))
            raise
