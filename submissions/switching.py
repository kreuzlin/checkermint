"""Switching to a newer task version (brief 5.4, ADR 0010, ADR 0011).

Only the participant switches, explicitly and after a confirmation that
lists what cannot be carried over. The attempt then pins the latest
published version. A draft keeps its version for good (ADR 0010), so the
draft is replaced: a new draft on the new version gets copies of the items
whose requirement exists there with the same key and type (up to the new
maximum count); the old draft and its other items are deleted.

Submissions already submitted keep their version. Granted hints stay
granted where the new version has a hint with the same key (#38,
`hints.services.plan_carry_over`); the confirmation lists them and the
granted hints that are lost. An open hint request for a hint the new
version no longer has blocks the switch until a coach decided it.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from hints.services import HintCarryOver, plan_carry_over
from tasks.models import TaskAttempt, TaskVersion

from .models import Submission, SubmissionItem
from .services import copy_file, get_draft


class SwitchNotPossible(Exception):
    pass


OPEN_REQUEST_BLOCKS = (
    "Deine Hinweis-Anfrage gilt für einen Hinweis, den es in der neuen Version "
    "nicht mehr gibt. Warte auf die Antwort eines Coachs, dann kannst du wechseln."
)


@dataclass
class Dropped:
    requirement_label: str
    count: int
    reason: str


@dataclass
class SwitchPlan:
    attempt: TaskAttempt
    current: TaskVersion
    target: TaskVersion
    newer_versions: list[TaskVersion]  # current+1 … target, for change notes
    draft: Submission | None
    carried: list[tuple[SubmissionItem, object]] = field(default_factory=list)
    dropped: list[Dropped] = field(default_factory=list)
    hints: HintCarryOver = field(default_factory=HintCarryOver)


def newer_version(attempt: TaskAttempt | None) -> TaskVersion | None:
    """The latest published version if it is newer than the pinned one."""
    if attempt is None:
        return None
    latest = attempt.task.latest_published_version()
    if latest is None or latest.number <= attempt.task_version.number:
        return None
    return latest


def plan_switch(user, task) -> SwitchPlan:
    attempt = (
        TaskAttempt.objects.select_related("task_version", "task")
        .filter(user=user, task=task)
        .first()
    )
    target = newer_version(attempt)
    if target is None:
        raise SwitchNotPossible("Es gibt keine neuere Version dieser Aufgabe.")
    current = attempt.task_version
    plan = SwitchPlan(
        attempt=attempt,
        current=current,
        target=target,
        newer_versions=list(
            task.versions.published()
            .filter(number__gt=current.number, number__lte=target.number)
            .order_by("number")
        ),
        draft=get_draft(user, task),
        hints=plan_carry_over(attempt, target),
    )
    if plan.draft is None:
        return plan

    new_requirements = {r.key: r for r in target.requirements.all()}
    items = plan.draft.items.select_related("requirement").order_by(
        "requirement__order", "requirement", "order", "pk"
    )
    by_requirement: dict[int, list[SubmissionItem]] = {}
    for item in items:
        by_requirement.setdefault(item.requirement_id, []).append(item)
    for group in by_requirement.values():
        old = group[0].requirement
        new = new_requirements.get(old.key)
        if new is None:
            plan.dropped.append(
                Dropped(
                    old.label, len(group), "gibt es in der neuen Version nicht mehr"
                )
            )
            continue
        if new.type != old.type:
            plan.dropped.append(
                Dropped(old.label, len(group), f"ist jetzt «{new.get_type_display()}»")
            )
            continue
        plan.carried.extend((item, new) for item in group[: new.max_count])
        extra = len(group) - new.max_count
        if extra > 0:
            plan.dropped.append(
                Dropped(old.label, extra, f"neu sind höchstens {new.max_count} erlaubt")
            )
    return plan


def switch_version(user, task, target_id: int) -> TaskAttempt:
    """Switch to `target_id` (the version the participant confirmed).

    Refuses if the latest version changed since the confirmation, so nobody
    switches to something they have not seen.
    """
    with transaction.atomic():
        TaskAttempt.objects.select_for_update().filter(user=user, task=task).first()
        plan = plan_switch(user, task)
        if plan.target.pk != target_id:
            raise SwitchNotPossible(
                "Inzwischen gibt es eine andere Version. Schau sie dir zuerst an."
            )
        if plan.hints.blocks_switch:
            raise SwitchNotPossible(OPEN_REQUEST_BLOCKS)
        if plan.draft is not None:
            # Read everything to keep before the old draft (and its files)
            # goes; each item owns its files (ADR 0014).
            copies = [
                {
                    "requirement": new_requirement,
                    "order": item.order,
                    "text": item.text,
                    "original_filename": item.original_filename,
                    "data": item.data,
                    "file": copy_file(item.file) or "",
                    "thumbnail": copy_file(item.thumbnail) or "",
                    "uploaded_by_id": item.uploaded_by_id,
                    "via_phone": item.via_phone,
                }
                for item, new_requirement in plan.carried
            ]
            for item in plan.draft.items.all():
                item.delete()  # deletes its files on commit
            plan.draft.delete()
            new_draft = Submission.objects.create(
                user=user, task=task, task_version=plan.target
            )
            for order_in_requirement, values in _renumber(copies):
                SubmissionItem.objects.create(
                    submission=new_draft, **{**values, "order": order_in_requirement}
                )
        attempt = plan.attempt
        attempt.task_version = plan.target
        attempt.switched_at = timezone.now()
        attempt.save(update_fields=["task_version", "switched_at"])
        return attempt


def _renumber(copies):
    """Orders 0, 1, … per requirement (some items may have been dropped)."""
    counters: dict[int, int] = {}
    for values in copies:
        requirement_id = values["requirement"].pk
        order = counters.get(requirement_id, 0)
        counters[requirement_id] = order + 1
        yield order, values
