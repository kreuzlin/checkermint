"""Task detail for coaches (brief 5.10.4, #41).

Who solved the task (best approved submission per active participant, with
its version), the average of those best stars, how often each hint was
requested, granted and declined, and every version with its change note
and the number of participants pinned to it.

Hints are counted by key, so a hint that keeps its key across versions is
one row (the same rule as granted hints, brief 5.5).
"""

from dataclasses import dataclass

from django.db.models import Count, Q

from accounts.views import participant_profiles
from hints.models import HintRequest
from submissions.models import Submission
from tasks.models import Hint, Task, TaskVersion


@dataclass(frozen=True)
class Solver:
    profile: object  # accounts.Profile
    submission: Submission  # best approved: most stars, then earliest


@dataclass(frozen=True)
class HintStats:
    hint: Hint  # from the newest version that has the key
    requested: int
    granted: int
    declined: int
    open: int


@dataclass(frozen=True)
class TaskDetail:
    task: Task
    title: str
    solvers: list[Solver]
    average_stars: float | None
    hints: list[HintStats]
    versions: list[TaskVersion]  # newest first, with `pinned`


def task_detail(task: Task) -> TaskDetail:
    versions = list(
        TaskVersion.objects.filter(task=task)
        .annotate(pinned=Count("attempts"))
        .order_by("-number")
    )
    published = [v for v in versions if v.status == TaskVersion.Status.PUBLISHED]
    title = (published or versions)[0].title if versions else task.slug
    solvers = _solvers(task)
    average = (
        sum(s.submission.stars for s in solvers) / len(solvers) if solvers else None
    )
    return TaskDetail(
        task=task,
        title=title,
        solvers=solvers,
        average_stars=average,
        hints=_hint_stats(task),
        versions=versions,
    )


def _solvers(task: Task) -> list[Solver]:
    profiles = {p.user_id: p for p in participant_profiles()}
    best: dict[int, Submission] = {}
    approved = (
        Submission.objects.filter(
            task=task, status=Submission.Status.APPROVED, user__in=profiles
        )
        .select_related("task_version")
        .order_by("-stars", "reviewed_at", "pk")
    )
    for submission in approved:
        best.setdefault(submission.user_id, submission)
    solvers = [Solver(profiles[user_id], s) for user_id, s in best.items()]
    return sorted(solvers, key=lambda s: s.profile.nickname.lower())


def _hint_stats(task: Task) -> list[HintStats]:
    status = HintRequest.Status
    counts = {
        row["hint__key"]: row
        for row in HintRequest.objects.filter(task_attempt__task=task)
        .values("hint__key")
        .annotate(
            requested=Count("pk"),
            granted=Count("pk", filter=Q(status=status.GRANTED)),
            declined=Count("pk", filter=Q(status=status.DECLINED)),
            open=Count("pk", filter=Q(status=status.OPEN)),
        )
    }
    # Newest version first, so each key shows its current text and order.
    hints: dict[str, Hint] = {}
    for hint in (
        Hint.objects.filter(task_version__task=task)
        .select_related("task_version")
        .order_by("-task_version__number", "order", "pk")
    ):
        hints.setdefault(hint.key, hint)
    empty = {"requested": 0, "granted": 0, "declined": 0, "open": 0}
    return [
        HintStats(
            hint=hint,
            **{k: counts.get(key, empty)[k] for k in empty},
        )
        for key, hint in hints.items()
    ]
