"""Coach queue: everything waiting for a coach, oldest first (brief 5.10.1).

For now the queue holds submissions to review. Hint requests (#37) join as
a second kind of entry; the queue is then merged and sorted by
`waiting_since`.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Exists, OuterRef

from .models import Submission


@dataclass(frozen=True)
class QueueEntry:
    kind: str  # "submission"; "hint_request" follows with #37
    waiting_since: datetime
    submission: Submission
    is_resubmission: bool


def queue_entries() -> list[QueueEntry]:
    """Submitted, unreviewed solutions of active participants, oldest first."""
    earlier = Submission.objects.filter(
        user=OuterRef("user"),
        task=OuterRef("task"),
        submitted_at__lt=OuterRef("submitted_at"),
    )
    submissions = (
        Submission.objects.filter(
            status=Submission.Status.SUBMITTED, user__is_active=True
        )
        .annotate(is_resubmission=Exists(earlier))
        .select_related("user__profile", "task__topic", "task_version")
        .order_by("submitted_at", "pk")
    )
    return [
        QueueEntry(
            kind="submission",
            waiting_since=submission.submitted_at,
            submission=submission,
            is_resubmission=submission.is_resubmission,
        )
        for submission in submissions
    ]
