"""Points and levels, always computed from reviews (brief 5.8, ADR 0013).

- Points for a task: the best approved submission for it,
  `base points of its version × stars`. A later, worse review never lowers
  them, because the maximum counts.
- Points per topic: the sum over all tasks of the topic, archived and
  hidden tasks included (points once earned stay).
- Level per topic: from the shared threshold table (`tasks.levels`).

Nothing here is stored; dashboard, catalogue, coach views and ranking all
use these functions so they always agree.
"""

from dataclasses import dataclass

from django.db.models import F, Max

from tasks.levels import LevelInfo, level_for_points, thresholds
from tasks.models import Topic

from .models import Submission


def approved(user):
    return Submission.objects.filter(user=user, status=Submission.Status.APPROVED)


def points_by_task(user) -> dict[int, int]:
    """Task id → points of the best approved submission (one query)."""
    return points_by_task_queryset(approved(user))


def task_points(user, task) -> int | None:
    """Points for one task, None without an approved submission."""
    return points_by_task_queryset(approved(user).filter(task=task)).get(task.pk)


def points_by_task_queryset(submissions) -> dict[int, int]:
    rows = (
        submissions.values("task_id")
        .annotate(best=Max(F("task_version__base_points") * F("stars")))
        .values_list("task_id", "best")
    )
    return dict(rows)


def points_by_topic(user) -> dict[int, int]:
    """Topic id → sum of the task points in that topic (one query)."""
    totals: dict[int, int] = {}
    rows = (
        approved(user)
        .values("task_id", "task__topic_id")
        .annotate(best=Max(F("task_version__base_points") * F("stars")))
        .values_list("task__topic_id", "best")
    )
    for topic_id, best in rows:
        totals[topic_id] = totals.get(topic_id, 0) + best
    return totals


def levels_by_topic(user, topic_ids) -> dict[int, LevelInfo]:
    """Level, points and next threshold per topic id (two queries)."""
    table = thresholds()
    points = points_by_topic(user)
    return {
        topic_id: level_for_points(points.get(topic_id, 0), table)
        for topic_id in topic_ids
    }


@dataclass(frozen=True)
class TopicProgress:
    topic: Topic
    level: LevelInfo


def topic_progress(user) -> list[TopicProgress]:
    """Every topic in display order with the user's level and points."""
    topics = list(Topic.objects.all())
    levels = levels_by_topic(user, [topic.pk for topic in topics])
    return [TopicProgress(topic=topic, level=levels[topic.pk]) for topic in topics]
