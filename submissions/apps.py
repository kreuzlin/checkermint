from django.apps import AppConfig


def can_access_item(user, item) -> bool:
    """The participant who owns the submission, and coaches (ADR 0009)."""
    from accounts.roles import is_coach

    if not user.is_authenticated:
        return False
    return item.submission.user_id == user.pk or is_coach(user)


def item_file(item_type, variants):
    def get_file(item, variant):
        if item.requirement.type != item_type or variant not in variants:
            return None
        return item.thumbnail if variant == "vorschau" else item.file

    return get_file


class SubmissionsConfig(AppConfig):
    name = "submissions"
    verbose_name = "Einreichungen"

    def ready(self):
        from core import private_files

        from .models import SubmissionItem

        private_files.register(
            "einreichungsfoto",
            private_files.PrivateFileKind(
                model=SubmissionItem,
                get_file=item_file("photo", {None, "vorschau"}),
                can_access=can_access_item,
                # Re-encoded by core.images, so it may be shown inline.
                inline=True,
                get_filename=lambda item: item.original_filename,
            ),
        )
        private_files.register(
            "einreichungsdatei",
            private_files.PrivateFileKind(
                model=SubmissionItem,
                get_file=item_file("file", {None}),
                can_access=can_access_item,
                # Raw uploads: always a download (attachment).
                inline=False,
                get_filename=lambda item: item.original_filename,
            ),
        )
