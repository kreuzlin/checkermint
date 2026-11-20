"""Draft, submit and resubmit (brief 5.6, ADR 0010, ADR 0011).

A participant has at most one draft per task. Saving the first draft
starts the task (pins the version). While a submission waits for a coach,
no new draft can be made; after "needs revision" or "approved" a new draft
starts from the last submission's content.
"""

from pathlib import PurePath

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from badges.awards import award_for
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
    for item in submission.items.select_related("submission").order_by("order", "pk"):
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


def save_draft(
    user, task, items: dict[int, list[dict]], uploaded_by=None
) -> Submission:
    """Create or update the draft with the items per requirement id.

    Requirements missing from `items` (types without a handler) keep their
    stored items. Starts the task if needed. New items are recorded as
    added by `uploaded_by` (default: the participant).
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
            store_items(
                user, draft, requirement_id, values, uploaded_by=uploaded_by or user
            )
        return draft


def store_items(
    user, draft, requirement_id, values, uploaded_by=None, via_phone=False
) -> None:
    """Make the draft's items for one requirement match `values`.

    Kept items of the draft stay (only their order changes), kept items of an
    earlier submission are copied with their files, dicts become new items,
    and the draft's other items are deleted.
    """
    kept = {
        value.pk
        for value in values
        if isinstance(value, SubmissionItem) and value.submission_id == draft.pk
    }
    for old in draft.items.filter(requirement_id=requirement_id):
        if old.pk not in kept:
            old.delete()
    for order, value in enumerate(values):
        if not isinstance(value, SubmissionItem):
            SubmissionItem.objects.create(
                submission=draft,
                requirement_id=requirement_id,
                order=order,
                uploaded_by=uploaded_by,
                via_phone=via_phone,
                **value,
            )
        elif value.submission_id == draft.pk:
            if value.order != order:
                value.order = order
                value.save(update_fields=["order"])
        else:
            if (
                value.requirement_id != requirement_id
                or value.submission.user_id != user.pk
            ):
                raise ValueError("Only the participant's own items can be kept.")
            copy_item(value, draft, order)


def copy_file(field):
    """A new, unsaved copy of a stored file (each item owns its files)."""
    if not field:
        return None
    with field.open("rb") as source:
        return ContentFile(source.read(), name=PurePath(field.name).name)


def copy_item(item, draft, order) -> SubmissionItem:
    return SubmissionItem.objects.create(
        submission=draft,
        requirement_id=item.requirement_id,
        order=order,
        text=item.text,
        original_filename=item.original_filename,
        data=item.data,
        file=copy_file(item.file) or "",
        thumbnail=copy_file(item.thumbnail) or "",
        uploaded_by_id=item.uploaded_by_id,
        via_phone=item.via_phone,
    )


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


def add_to_draft(
    draft: Submission, items: dict[int, list], uploaded_by=None, via_phone=False
) -> None:
    """Store uploads from the phone page or a coach in the draft (still a
    draft?). `uploaded_by` / `via_phone` record who added them (#77)."""
    with transaction.atomic():
        locked = Submission.objects.select_for_update().filter(pk=draft.pk).first()
        if locked is None or not locked.is_draft:
            raise SubmissionNotAllowed("Dieser Entwurf ist schon eingereicht.")
        for requirement_id, values in items.items():
            store_items(
                locked.user,
                locked,
                requirement_id,
                values,
                uploaded_by=uploaded_by,
                via_phone=via_phone,
            )


def ensure_draft(user, task) -> Submission:
    """The participant's draft, created if needed (e.g. for a coach upload).

    A new draft starts the task and, like the form, starts from the last
    submission against the same version (copies of all its items).
    """
    with transaction.atomic():
        draft = get_draft(user, task)
        if draft is not None:
            return draft
        if is_waiting(user, task):
            raise SubmissionNotAllowed("Die Lösung wartet noch auf einen Coach.")
        version = start_attempt(user, task).task_version
        previous = starting_content(user, task, version)
        return save_draft(
            user, task, {pk: list(items) for pk, items in previous.items()}
        )


def review_submission(
    submission: Submission, coach, status: str, stars: int | None, feedback: str
) -> Submission:
    """Submitted → approved (with stars) or needs revision (brief 5.8).

    Locks the row, so two coaches cannot review the same submission. Points
    and levels follow from the data (#33); an approval awards the task's
    badge in the same transaction (#34).
    """
    if status not in Submission.REVIEWED:
        raise ValueError("A review either approves or asks for a revision.")
    with transaction.atomic():
        locked = Submission.objects.select_for_update().get(pk=submission.pk)
        if locked.status != Submission.Status.SUBMITTED:
            raise SubmissionNotAllowed("Diese Lösung hat schon jemand bewertet.")
        locked.status = status
        locked.stars = stars if status == Submission.Status.APPROVED else None
        locked.feedback = feedback
        locked.reviewed_by = coach
        locked.reviewed_at = timezone.now()
        locked.full_clean()
        locked.save()
        award_for(locked)
        return locked
