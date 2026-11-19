"""Participant dashboard on the home page (brief 5.9, #35).

Built from the same sources as the catalogue and the progress service, so
levels, statuses and points always agree with the other pages.
"""

from dataclasses import dataclass

from badges.awards import recent_badges
from tasks.catalogue import (
    CatalogueEntry,
    Status,
    TopicSection,
    catalogue,
    visible_tasks,
)

from .models import Submission

SUGGESTIONS = 4
RECENTLY_APPROVED = 5


@dataclass(frozen=True)
class Dashboard:
    sections: list[TopicSection]  # levels per topic (topics with visible tasks)
    revisions: list[Submission]  # latest submission per task asks for revision
    waiting: int  # submissions waiting for a coach
    approved: list[Submission]  # newest reviews first, with `points`
    suggestions: list[CatalogueEntry]
    recent_badges: list


def open_revisions(user) -> list[Submission]:
    """Tasks whose latest submission came back with "needs revision",
    oldest review first (waiting longest)."""
    latest: dict[int, Submission] = {}
    submissions = (
        Submission.objects.filter(user=user, task__in=visible_tasks())
        .exclude(status=Submission.Status.DRAFT)
        .select_related("task", "task__topic", "task_version", "reviewed_by__profile")
        .order_by("task_id", "-submitted_at")
    )
    for submission in submissions:
        latest.setdefault(submission.task_id, submission)
    revisions = [
        s for s in latest.values() if s.status == Submission.Status.NEEDS_REVISION
    ]
    return sorted(revisions, key=lambda s: s.reviewed_at)


def recently_approved(user, limit=RECENTLY_APPROVED) -> list[Submission]:
    submissions = list(
        Submission.objects.filter(user=user, status=Submission.Status.APPROVED)
        .select_related("task", "task__topic", "task_version")
        .order_by("-reviewed_at")[:limit]
    )
    for submission in submissions:
        submission.points = submission.task_version.base_points * submission.stars
    return submissions


def suggested_tasks(sections, limit=SUGGESTIONS) -> list[CatalogueEntry]:
    """Started tasks first, then open ones with the lowest minimum level
    (brief 5.10.3), in catalogue order otherwise. Locked, waiting, solved
    and revision tasks are left out (revisions have their own list)."""
    entries = [e for section in sections for e in section.entries]
    started = [e for e in entries if e.status is Status.STARTED]
    open_ = [e for e in entries if e.status is Status.OPEN]
    open_.sort(key=lambda e: e.task.min_level)  # stable: keeps catalogue order
    return (started + open_)[:limit]


def dashboard(user) -> Dashboard:
    sections = catalogue(user)
    return Dashboard(
        sections=sections,
        revisions=open_revisions(user),
        waiting=Submission.objects.filter(
            user=user, status=Submission.Status.SUBMITTED
        ).count(),
        approved=recently_approved(user),
        suggestions=suggested_tasks(sections),
        recent_badges=list(recent_badges()),
    )
