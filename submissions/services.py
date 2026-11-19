"""Draft, submit and resubmit (brief 5.6, ADR 0010, ADR 0011).

A participant has at most one draft per task. Saving the first draft
starts the task (pins the version). While a submission waits for a coach,
no new draft can be made; after "needs revision" or "approved" a new draft
starts from the last submission's content.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from tasks.attempts import start_attempt

from .models import Submission, SubmissionItem


def get_draft(user, task) -> Submission | None:
    return (
        Submission.objects.filter(user=user, task=task, status=Submission.Status.DRAFT)
        .select_related("task_version")
        .first()
    )


def submitted_submissions(user, task):
    """Non-draft submissions of the user for the task, newest first."""
    return (
        Submission.objects.filter(user=user, task=task)
        .exclude(status=Submission.Status.DRAFT)
        .select_related("task_version", "reviewed_by__profile")
        .prefetch_related("items__requirement")
        .order_by("-submitted_at")
    )


def is_waiting(user, task) -> bool:
    """The latest submission waits for a coach."""
    latest = submitted_submissions(user, task).first()
    return latest is not None and latest.status == Submission.Status.SUBMITTED


def items_by_requirement(submission) -> dict[int, list[SubmissionItem]]:
    result: dict[int, list[SubmissionItem]] = {}
    if submission is None:
        return result
    for item in submission.items.order_by("order", "pk"):
        result.setdefault(item.requirement_id, []).append(item)
    return result


def starting_content(user, task, version) -> dict[int, list[SubmissionItem]]:
    """What the form shows: the draft, otherwise the last submission against
    the same version (resubmission), otherwise nothing."""
    draft = get_draft(user, task)
    if draft is not None:
        return items_by_requirement(draft)
    latest = submitted_submissions(user, task).first()
    if latest is not None and latest.task_version_id == version.pk:
        return items_by_requirement(latest)
    return {}


class SubmissionNotAllowed(Exception):
    pass


def save_draft(user, task, items: dict[int, list[dict]]) -> Submission:
    """Create or update the draft with the items per requirement id.

    Requirements missing from `items` (types without a handler) keep their
    stored items. Starts the task if needed.
    """
    with transaction.atomic():
        if is_waiting(user, task):
            raise SubmissionNotAllowed("Deine Lösung wartet noch auf einen Coach.")
        attempt = start_attempt(user, task)
        draft = (
            Submission.objects.select_for_update()
            .filter(user=user, task=task, status=Submission.Status.DRAFT)
            .first()
        )
        if draft is None:
            try:
                with transaction.atomic():
                    draft = Submission.objects.create(
                        user=user, task=task, task_version=attempt.task_version
                    )
            except IntegrityError:
                # Created at the same moment in another request.
                draft = Submission.objects.select_for_update().get(
                    user=user, task=task, status=Submission.Status.DRAFT
                )
        if draft.task_version_id != attempt.task_version_id:
            # Only possible once switching versions exists (#26).
            raise SubmissionNotAllowed("Die Version deines Entwurfs ist veraltet.")

        requirement_ids = set(
            draft.task_version.requirements.values_list("pk", flat=True)
        )
        for requirement_id, values in items.items():
            if requirement_id not in requirement_ids:
                raise ValueError("Requirement of another version.")
            for old in draft.items.filter(requirement_id=requirement_id):
                old.delete()
            for order, fields in enumerate(values):
                SubmissionItem.objects.create(
                    submission=draft,
                    requirement_id=requirement_id,
                    order=order,
                    **fields,
                )
        return draft


def submit(draft: Submission) -> Submission:
    """Draft → submitted. Completeness is checked by the form."""
    with transaction.atomic():
        draft = Submission.objects.select_for_update().get(pk=draft.pk)
        if not draft.is_draft:
            raise SubmissionNotAllowed("Diese Lösung ist schon eingereicht.")
        draft.status = Submission.Status.SUBMITTED
        draft.submitted_at = timezone.now()
        draft.save(update_fields=["status", "submitted_at"])
        return draft
