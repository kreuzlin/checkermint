"""A participant's history (brief 5.9): everything submitted and achieved,
newest first.

Events come from submissions: "eingereicht" when a solution was submitted,
and the review ("angenommen" with stars, "Überarbeitung nötig") when a
coach reviewed it. Badges join the history when they are awarded (#34).
"""

from dataclasses import dataclass
from datetime import datetime

from tasks.catalogue import visible_tasks

from .models import Submission


@dataclass(frozen=True)
class Event:
    when: datetime
    kind: str  # "submitted" or "reviewed"
    submission: Submission
    task_visible: bool

    @property
    def is_review(self) -> bool:
        return self.kind == "reviewed"


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
    events.sort(key=lambda event: (event.when, event.is_review), reverse=True)
    return events
