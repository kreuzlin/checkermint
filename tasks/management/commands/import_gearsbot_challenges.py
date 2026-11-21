"""`manage.py import_gearsbot_challenges`: GearsBot's Basic Challenges as
draft tasks (ADR 0021, #146). On the server only with the maintainer's OK."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from tasks.gearsbot_import import BUNDLE, TopicNameTaken, import_challenges


class Command(BaseCommand):
    help = (
        "Create or update one unpublished task per GearsBot Basic Challenge from "
        "the committed bundle. Idempotent; published versions are never changed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen; change nothing.",
        )
        parser.add_argument(
            "--bundle",
            type=Path,
            default=BUNDLE,
            help="Bundle directory (default: sim/gears/challenges_basic).",
        )

    def handle(self, *args, dry_run, bundle, **options):
        try:
            result = import_challenges(bundle, dry_run=dry_run)
        except TopicNameTaken as error:
            raise CommandError(str(error)) from None
        sections = [
            ("New tasks (unpublished drafts)", result.created),
            ("Drafts updated with the new world or code", result.updated_drafts),
            ("New draft versions (world or code changed upstream)", result.new_drafts),
            ("Unchanged", result.unchanged),
            ("Skipped", result.skipped),
            (
                "GearsBot tasks no longer in the bundle (left as they are)",
                result.missing_upstream,
            ),
        ]
        for title, items in sections:
            self.stdout.write(f"{title}: {len(items)}")
            if items and title != "Unchanged":
                for item in items:
                    self.stdout.write(f"  - {item}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing was saved."))
        else:
            self.stdout.write(self.style.SUCCESS("Done."))
