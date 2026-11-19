"""Task catalogue: which tasks a user sees and their status (brief 5.3, 5.9).

Visible are tasks that are published for participants and not archived.
A task is locked until the participant's level in its topic reaches the
task's minimum level; coaches see every visible task unlocked.

Statuses that need submissions (submitted, needs revision, solved) follow
with the submission models (#22) and reviews (#32).
"""

from dataclasses import dataclass
from enum import Enum

from django.db.models import Prefetch

from accounts.roles import is_coach

from .levels import level_for_points, thresholds
from .models import Task, TaskAttempt, TaskVersion, Topic


class Status(Enum):
    OPEN = "offen"
    STARTED = "begonnen"
    LOCKED = "gesperrt"

    @property
    def label(self) -> str:
        return {
            Status.OPEN: "Offen",
            Status.STARTED: "Begonnen",
            Status.LOCKED: "Gesperrt",
        }[self]


@dataclass(frozen=True)
class CatalogueEntry:
    task: Task
    version: TaskVersion  # pinned or latest published
    status: Status

    @property
    def is_locked(self) -> bool:
        return self.status is Status.LOCKED


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


def task_status(user, task: Task, level: int, started: bool) -> Status:
    if started:
        return Status.STARTED
    if not is_coach(user) and level < task.min_level:
        return Status.LOCKED
    return Status.OPEN


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
    levels = levels_by_topic(user, {task.topic_id for task in tasks})

    sections: list[TopicSection] = []
    for task in tasks:
        if not sections or sections[-1].topic.pk != task.topic_id:
            level = levels[task.topic_id]
            sections.append(TopicSection(topic=task.topic, level=level, entries=[]))
        version = pinned.get(task.pk) or task.published_versions[0]
        status = task_status(user, task, sections[-1].level, started=task.pk in pinned)
        sections[-1].entries.append(
            CatalogueEntry(task=task, version=version, status=status)
        )
    return sections
