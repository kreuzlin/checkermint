"""`manage.py seed_demo`: demo data for local development (see submissions.demo)."""

import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ProtectedError

from submissions.demo import (
    COACH,
    PARTICIPANTS,
    DemoDataExists,
    DemoNameTaken,
    has_demo_data,
    remove_demo_data,
    seed,
)


class Command(BaseCommand):
    help = (
        "Create demo data (coach, participants, tasks, submissions) for local "
        "development. Refuses to run unless DEBUG is on."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            help="Password for all demo accounts (default: a random one, printed).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data first.",
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Only delete the demo data.",
        )

    def handle(self, *args, password=None, reset=False, remove=False, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data only with DEBUG=true (never in production).")
        if reset or remove:
            try:
                remove_demo_data()
            except ProtectedError as error:
                raise CommandError(
                    "Demo tasks are used by non-demo accounts; delete those "
                    f"submissions first. ({error.args[0]})"
                ) from None
            self.stdout.write("Demo data removed.")
            if remove:
                return
        if has_demo_data():
            raise CommandError("Demo data exists already. Use --reset to recreate it.")
        password = password or secrets.token_urlsafe(9)
        try:
            seed(password)
        except DemoDataExists:
            raise CommandError("Demo data exists already.") from None
        except DemoNameTaken as error:
            raise CommandError(
                f"Names of the demo data are used by other data: {error}. "
                "Rename those first."
            ) from None
        users = [COACH[0]] + [username for username, *_ in PARTICIPANTS]
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(f"Accounts: {', '.join(users)} (coach: {COACH[0]})")
        self.stdout.write(f"Password for all of them: {password}")
