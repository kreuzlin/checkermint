"""Coach queue: everything waiting for a coach, oldest first (brief 5.10.1).

Two kinds of entries: submissions to review (#31) and hint requests to
grant or decline (#37), merged and sorted by `waiting_since`. Entries of
deactivated participants are left out.
"""

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Exists, OuterRef

from hints.models import HintRequest

from .models import Submission

SUBMISSION = "submission"
HINT_REQUEST = "hint_request"


@dataclass(frozen=True)
class QueueEntry:
    kind: str  # SUBMISSION or HINT_REQUEST
    waiting_since: datetime
    submission: Submission | None = None
    is_resubmission: bool = False
    hint_request: HintRequest | None = None


def submission_entries() -> list[QueueEntry]:
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
            kind=SUBMISSION,
            waiting_since=submission.submitted_at,
            submission=submission,
            is_resubmission=submission.is_resubmission,
        )
        for submission in submissions
    ]


def hint_request_entries() -> list[QueueEntry]:
    """Open hint requests of active participants, oldest first."""
    requests = (
        HintRequest.objects.filter(
            status=HintRequest.Status.OPEN, task_attempt__user__is_active=True
        )
        .select_related(
            "task_attempt__user__profile",
            "task_attempt__task__topic",
            "task_attempt__task_version",
            "hint__task_version",
        )
        .order_by("requested_at", "pk")
    )
    return [
        QueueEntry(
            kind=HINT_REQUEST,
            waiting_since=request.requested_at,
            hint_request=request,
        )
        for request in requests
    ]


def queue_entries() -> list[QueueEntry]:
    """Everything waiting for a coach, oldest first."""
    entries = submission_entries() + hint_request_entries()
    # Stable sort: ties keep submissions first, each kind in its own order.
    return sorted(entries, key=lambda entry: entry.waiting_since)
