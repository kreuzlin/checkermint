"""A participant's history (brief 5.9): everything submitted and achieved,
newest first.

Events come from submissions: "eingereicht" when a solution was submitted,
and the review ("angenommen" with stars, "Überarbeitung nötig") when a
coach reviewed it. Badges join the history when they are awarded (#34).
"""

from dataclasses import dataclass
from datetime import datetime

from badges.awards import badges_of
from badges.models import UserBadge
from tasks.catalogue import visible_tasks

from .models import Submission


@dataclass(frozen=True)
class Event:
    when: datetime
    kind: str  # "submitted", "reviewed" or "badge"
    submission: Submission | None
    task_visible: bool
    award: UserBadge | None = None

    @property
    def is_review(self) -> bool:
        return self.kind == "reviewed"

    @property
    def is_badge(self) -> bool:
        return self.kind == "badge"


def history_events(user) -> list[Event]:
    submissions = list(
        Submission.objects.filter(user=user)
        .exclude(status=Submission.Status.DRAFT)
        .select_related("task", "task__topic", "task_version", "reviewed_by__profile")
        .prefetch_related("items__requirement")
    )
    visible = set(
        visible_tasks()
        .filter(pk__in={s.task_id for s in submissions})
        .values_list("pk", flat=True)
    )
    events = []
    for submission in submissions:
        shown = submission.task_id in visible
        events.append(Event(submission.submitted_at, "submitted", submission, shown))
        if submission.reviewed_at:
            events.append(Event(submission.reviewed_at, "reviewed", submission, shown))
    for award in badges_of(user):
        events.append(Event(award.awarded_at, "badge", None, False, award))
    # Same moment: the badge above the review above the submission.
    order = {"submitted": 0, "reviewed": 1, "badge": 2}
    events.sort(key=lambda event: (event.when, order[event.kind]), reverse=True)
    return events
