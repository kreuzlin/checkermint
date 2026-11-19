"""Which task version a participant sees (brief 5.4, ADR 0010).

All "what does this participant see" queries go through `visible_version`,
so the pinning rule lives in one place.
"""

from django.db import IntegrityError, transaction

from .models import Task, TaskAttempt, TaskVersion


class TaskNotStartable(Exception):
    """The task cannot be started (not visible or nothing published)."""


def get_attempt(user, task: Task) -> TaskAttempt | None:
    if not user.is_authenticated:
        return None
    return (
        TaskAttempt.objects.select_related("task_version")
        .filter(user=user, task=task)
        .first()
    )


def visible_version(user, task: Task) -> TaskVersion | None:
    """The pinned version if the user has started the task, otherwise the
    latest published version (None if there is none)."""
    attempt = get_attempt(user, task)
    if attempt is not None:
        return attempt.task_version
    return task.latest_published_version()


def start_attempt(user, task: Task) -> TaskAttempt:
    """Start the task for `user`, pinning the latest published version.

    Idempotent: an existing attempt is returned unchanged (its version stays
    pinned). Used by "Aufgabe starten" (#20), the first draft submission
    (#23) and the first hint request (#36). Locking by level is checked by
    the caller, which knows the participant's points.
    """
    if not user.is_authenticated:
        raise TaskNotStartable("Nur angemeldete Teilnehmende können starten.")
    existing = get_attempt(user, task)
    if existing is not None:
        return existing
    if not task.is_published or task.is_archived:
        raise TaskNotStartable("Diese Aufgabe ist nicht verfügbar.")
    version = task.latest_published_version()
    if version is None:
        raise TaskNotStartable("Diese Aufgabe hat noch keine veröffentlichte Version.")
    try:
        with transaction.atomic():
            return TaskAttempt.objects.create(
                user=user, task=task, task_version=version
            )
    except IntegrityError:
        # Started at the same moment in another request (double click).
        return TaskAttempt.objects.get(user=user, task=task)
