"""Start the RDS instance from the command line, where waiting is fine (D-070).

`migrate`, `seed` and a deploy never pass through middleware, so they are the
one place a stopped database still surprises a person. This command is the
counterpart of the wake gate: same module, same AWS calls, plus the wait the
request path refuses to do.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.support.rds import DatabaseState, RdsInstance

LABELS = {
    DatabaseState.AVAILABLE: "available",
    DatabaseState.STOPPED: "stopped",
    DatabaseState.WAKING: "starting",
}


class Command(BaseCommand):
    help = (
        "Start the RDS instance named by RDS_INSTANCE_ID if it is stopped. "
        "With --wait, block until it accepts connections."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wait",
            action="store_true",
            help="Block until the instance is available (minutes, not seconds).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=900,
            help="How long --wait may take, in seconds (default: 900).",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=10,
            help="Seconds between status checks while waiting (default: 10).",
        )

    def handle(self, *args, **options):
        identifier = getattr(settings, "RDS_INSTANCE_ID", "")
        if not identifier:
            raise CommandError(
                "RDS_INSTANCE_ID is not set, so there is no instance to start. "
                "Local Postgres does not need this command."
            )

        instance = RdsInstance(
            identifier,
            region=getattr(settings, "AWS_REGION", None),
            available_ttl=settings.DATABASE_WAKE_AVAILABLE_TTL,
            waking_ttl=settings.DATABASE_WAKE_WAKING_TTL,
        )

        state = instance.refresh()
        self.stdout.write(f"{identifier}: {LABELS[state]}")
        if state is DatabaseState.STOPPED:
            instance.wake()
            state = DatabaseState.WAKING
        if state is DatabaseState.AVAILABLE:
            return

        if not options["wait"]:
            self.stdout.write("Starting. Run again with --wait to block until it is up.")
            return

        timeout = options["timeout"]
        self.stdout.write(f"Waiting up to {timeout}s for {identifier} (Ctrl-C leaves it starting).")
        became_available = instance.wait(
            timeout=timeout,
            interval=options["interval"],
            on_state=lambda seen: self.stdout.write(f"{identifier}: {LABELS[seen]}"),
        )
        if not became_available:
            raise CommandError(
                f"{identifier} was not available after {timeout}s. "
                "It keeps starting in the background; check the RDS console."
            )
        self.stdout.write(self.style.SUCCESS(f"{identifier}: available"))
