"""Progress matrix for coaches: participants × tasks (brief 5.10.2, #39).

Each cell is the participant's status for the task, computed with the same
rules as their own catalogue (`tasks.catalogue.task_state`): solved with
stars, submitted, needs revision, started, open or locked. Points and
levels come from approved submissions (ADR 0013). A fixed number of
queries, however many participants and tasks there are.
"""

from dataclasses import dataclass

from django.db.models import F, Max, Prefetch

from accounts.models import Profile
from accounts.views import participant_profiles
from submissions.models import Submission
from tasks.catalogue import TaskState, task_state, visible_tasks
from tasks.levels import level_for_points, thresholds
from tasks.models import Task, TaskAttempt, TaskVersion, Topic


@dataclass(frozen=True)
class Column:
    task: Task
    title: str  # of the latest published version


@dataclass(frozen=True)
class Row:
    profile: Profile
    cells: list[TaskState]
    level: int | None  # in the filtered topic, None without filter


@dataclass(frozen=True)
class Matrix:
    columns: list[Column]
    rows: list[Row]


def topics_with_tasks():
    """Topics that have at least one visible task (for the filter)."""
    return Topic.objects.filter(tasks__in=visible_tasks()).distinct()


def progress_matrix(topic: Topic | None = None) -> Matrix:
    tasks = visible_tasks().select_related("topic")
    if topic is not None:
        tasks = tasks.filter(topic=topic)
    tasks = list(
        tasks.prefetch_related(
            Prefetch(
                "versions",
                queryset=TaskVersion.objects.published().order_by("-number"),
                to_attr="published_versions",
            )
        ).order_by("topic__order", "topic__name", "order", "slug")
    )
    profiles = list(participant_profiles().order_by("nickname"))
    users = [profile.user_id for profile in profiles]

    started = set(
        TaskAttempt.objects.filter(user__in=users, task__in=tasks).values_list(
            "user_id", "task_id"
        )
    )
    submitted: dict[tuple[int, int], list[tuple[str, int | None]]] = {}
    rows = (
        Submission.objects.filter(user__in=users, task__in=tasks)
        .exclude(status=Submission.Status.DRAFT)
        .order_by("-submitted_at")
        .values_list("user_id", "task_id", "status", "stars")
    )
    for user_id, task_id, status, stars in rows:
        submitted.setdefault((user_id, task_id), []).append((status, stars))
    points = _points_by_user_and_topic(users)
    table = thresholds()

    def level(user_id, topic_id):
        return level_for_points(points.get((user_id, topic_id), 0), table).level

    return Matrix(
        columns=[Column(task, task.published_versions[0].title) for task in tasks],
        rows=[
            Row(
                profile=profile,
                cells=[
                    task_state(
                        task,
                        level(profile.user_id, task.topic_id),
                        started=(profile.user_id, task.pk) in started,
                        submitted=submitted.get((profile.user_id, task.pk), ()),
                    )
                    for task in tasks
                ],
                level=level(profile.user_id, topic.pk) if topic else None,
            )
            for profile in profiles
        ],
    )


def _points_by_user_and_topic(users) -> dict[tuple[int, int], int]:
    """(user id, topic id) → points, like `submissions.progress` (one query)."""
    totals: dict[tuple[int, int], int] = {}
    rows = (
        Submission.objects.filter(user__in=users, status=Submission.Status.APPROVED)
        .values("user_id", "task_id", "task__topic_id")
        .annotate(best=Max(F("task_version__base_points") * F("stars")))
        .values_list("user_id", "task__topic_id", "best")
    )
    for user_id, topic_id, best in rows:
        totals[(user_id, topic_id)] = totals.get((user_id, topic_id), 0) + best
    return totals
