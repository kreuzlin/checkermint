"""Task catalogue: which tasks a user sees and their status (brief 5.3, 5.9).

Visible are tasks that are published for participants and not archived.
A task is locked until the participant's level in its topic reaches the
task's minimum level; coaches see every visible task unlocked.

The status comes from the participant's submissions (drafts do not count):
a submission waiting for a coach wins, then "solved" (any approved
submission, with the best stars), then "needs revision", then "started"
(an attempt exists), "open" or "locked".
"""

from dataclasses import dataclass
from enum import Enum

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404

from accounts.roles import is_coach
from submissions.models import Submission

from .attempts import get_attempt
from .levels import level_for_points, thresholds
from .models import Task, TaskAttempt, TaskVersion, Topic


class Status(Enum):
    OPEN = "offen"
    STARTED = "begonnen"
    SUBMITTED = "eingereicht"
    NEEDS_REVISION = "ueberarbeiten"
    SOLVED = "geloest"
    LOCKED = "gesperrt"

    @property
    def label(self) -> str:
        return {
            Status.OPEN: "Offen",
            Status.STARTED: "Begonnen",
            Status.SUBMITTED: "Eingereicht",
            Status.NEEDS_REVISION: "Überarbeitung nötig",
            Status.SOLVED: "Gelöst",
            Status.LOCKED: "Gesperrt",
        }[self]


@dataclass(frozen=True)
class TaskState:
    status: Status
    stars: int | None = None  # best stars if solved

    @property
    def is_locked(self) -> bool:
        return self.status is Status.LOCKED

    @property
    def star_symbols(self) -> str:
        return "★" * (self.stars or 0)


@dataclass(frozen=True)
class CatalogueEntry:
    task: Task
    version: TaskVersion  # pinned or latest published
    state: TaskState

    @property
    def status(self) -> Status:
        return self.state.status

    @property
    def is_locked(self) -> bool:
        return self.state.is_locked


@dataclass(frozen=True)
class TopicSection:
    topic: Topic
    level: int
    entries: list[CatalogueEntry]


def visible_tasks():
    """Tasks participants may see: published, not archived."""
    return Task.objects.filter(
        is_published=True, is_archived=False, versions__status="published"
    ).distinct()


def points_by_topic(user) -> dict[int, int]:
    """Points per topic id. Computed from approved submissions with #33;
    until then everybody has 0 points (level 1)."""
    return {}


def levels_by_topic(user, topic_ids) -> dict[int, int]:
    table = thresholds()
    points = points_by_topic(user)
    return {
        topic_id: level_for_points(points.get(topic_id, 0), table).level
        for topic_id in topic_ids
    }


def submitted_by_task(user, tasks) -> dict[int, list[tuple[str, int | None]]]:
    """(status, stars) of the user's non-draft submissions per task id,
    newest first."""
    result: dict[int, list[tuple[str, int | None]]] = {}
    rows = (
        Submission.objects.filter(user=user, task__in=tasks)
        .exclude(status=Submission.Status.DRAFT)
        .order_by("-submitted_at")
        .values_list("task_id", "status", "stars")
    )
    for task_id, status, stars in rows:
        result.setdefault(task_id, []).append((status, stars))
    return result


def task_state(user, task: Task, level: int, started: bool, submitted=()) -> TaskState:
    """`submitted`: (status, stars) of non-draft submissions, newest first."""
    if submitted:
        if submitted[0][0] == Submission.Status.SUBMITTED:
            return TaskState(Status.SUBMITTED)
        stars = [s for status, s in submitted if status == Submission.Status.APPROVED]
        if stars:
            return TaskState(Status.SOLVED, stars=max(stars))
        return TaskState(Status.NEEDS_REVISION)
    if started:
        return TaskState(Status.STARTED)
    if not is_coach(user) and level < task.min_level:
        return TaskState(Status.LOCKED)
    return TaskState(Status.OPEN)


def task_for(user, slug):
    """A visible task, the user's attempt and the task's state (404 if the
    task is not visible)."""
    task = get_object_or_404(visible_tasks().select_related("topic"), slug=slug)
    attempt = get_attempt(user, task)
    level = levels_by_topic(user, [task.topic_id])[task.topic_id]
    state = task_state(
        user,
        task,
        level,
        started=attempt is not None,
        submitted=submitted_by_task(user, [task]).get(task.pk, ()),
    )
    return task, attempt, state


def catalogue(user) -> list[TopicSection]:
    """Visible tasks grouped by topic (topic order, then task order).

    Topics without visible tasks are left out.
    """
    tasks = list(
        visible_tasks()
        .select_related("topic")
        .prefetch_related(
            Prefetch(
                "versions",
                queryset=TaskVersion.objects.published().order_by("-number"),
                to_attr="published_versions",
            )
        )
        .order_by("topic__order", "topic__name", "order", "slug")
    )
    pinned = {
        attempt.task_id: attempt.task_version
        for attempt in TaskAttempt.objects.filter(
            user=user, task__in=tasks
        ).select_related("task_version")
    }
    submitted = submitted_by_task(user, tasks)
    levels = levels_by_topic(user, {task.topic_id for task in tasks})

    sections: list[TopicSection] = []
    for task in tasks:
        if not sections or sections[-1].topic.pk != task.topic_id:
            level = levels[task.topic_id]
            sections.append(TopicSection(topic=task.topic, level=level, entries=[]))
        version = pinned.get(task.pk) or task.published_versions[0]
        state = task_state(
            user,
            task,
            sections[-1].level,
            started=task.pk in pinned,
            submitted=submitted.get(task.pk, ()),
        )
        sections[-1].entries.append(
            CatalogueEntry(task=task, version=version, state=state)
        )
    return sections
