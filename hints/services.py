"""Hint requests for participants (brief 5.5, #36).

The participant always asks for the *next* hint: the first hint of the
pinned version (in order) that is not granted yet. "Granted" is decided by
the hint's key, so a hint granted on an older version stays granted after a
switch when the new version has a hint with the same key (#38).
"""

from dataclasses import dataclass, field

from django.db import IntegrityError, transaction
from django.utils import timezone

from tasks.attempts import start_attempt
from tasks.models import Hint, Task, TaskAttempt, TaskVersion

from .models import HintRequest


class HintRequestNotAllowed(Exception):
    """The request cannot be made; the message is shown to the participant."""


@dataclass
class GrantedHint:
    hint: Hint
    request: HintRequest


@dataclass
class HintState:
    """What the participant sees of the hints of one task."""

    total: int
    granted: list[GrantedHint] = field(default_factory=list)
    next_hint: Hint | None = None
    open_request: HintRequest | None = None
    last_declined: HintRequest | None = None

    @property
    def can_request(self) -> bool:
        return self.next_hint is not None and self.open_request is None


def granted_requests(attempt: TaskAttempt) -> dict[str, HintRequest]:
    """The latest granted request per hint key of this attempt."""
    granted = {}
    requests = attempt.hint_requests.filter(
        status=HintRequest.Status.GRANTED
    ).select_related("hint", "decided_by__profile")
    for request in requests.order_by("decided_at", "pk"):
        granted[request.hint.key] = request
    return granted


def next_hint(attempt: TaskAttempt) -> Hint | None:
    granted = granted_requests(attempt)
    return attempt.task_version.hints.exclude(key__in=granted).first()


def hint_state(attempt: TaskAttempt | None, version: TaskVersion) -> HintState:
    hints = list(version.hints.all())
    state = HintState(total=len(hints))
    if attempt is None:
        state.next_hint = hints[0] if hints else None
        return state
    granted = granted_requests(attempt)
    state.granted = [
        GrantedHint(hint=hint, request=granted[hint.key])
        for hint in hints
        if hint.key in granted
    ]
    state.next_hint = next((h for h in hints if h.key not in granted), None)
    latest = attempt.hint_requests.select_related("hint").first()
    if latest is not None and latest.is_open:
        state.open_request = latest
    elif latest is not None and latest.status == HintRequest.Status.DECLINED:
        state.last_declined = latest
    return state


def request_hint(user, task: Task, message: str = "") -> HintRequest:
    """Ask for the next hint; starts the task if needed (brief 5.4).

    The caller checks that the user is a participant and the task is not
    locked (like `start_attempt`).
    """
    attempt = start_attempt(user, task)
    with transaction.atomic():
        # Serialise requests of the same attempt (double click).
        attempt = TaskAttempt.objects.select_for_update().get(pk=attempt.pk)
        if attempt.hint_requests.filter(status=HintRequest.Status.OPEN).exists():
            raise HintRequestNotAllowed("Deine Anfrage wartet noch auf einen Coach.")
        hint = next_hint(attempt)
        if hint is None:
            raise HintRequestNotAllowed("Du hast schon alle Hinweise erhalten.")
        try:
            with transaction.atomic():
                return HintRequest.objects.create(
                    task_attempt=attempt, hint=hint, message=message.strip()
                )
        except IntegrityError as error:
            raise HintRequestNotAllowed(
                "Deine Anfrage wartet noch auf einen Coach."
            ) from error


def decide_request(
    request: HintRequest, coach, status: str, reply: str = ""
) -> HintRequest:
    """Grant or decline an open request (brief 5.5, #37).

    Locks the row, so two coaches deciding at the same moment cannot both
    win; the second gets HintRequestNotAllowed. The caller checks that
    `coach` is a coach.
    """
    if status not in (HintRequest.Status.GRANTED, HintRequest.Status.DECLINED):
        raise ValueError(f"Not a decision: {status}")
    with transaction.atomic():
        request = HintRequest.objects.select_for_update().get(pk=request.pk)
        if not request.is_open:
            raise HintRequestNotAllowed("Diese Anfrage ist schon entschieden.")
        request.status = status
        request.coach_reply = reply.strip()
        request.decided_by = coach
        request.decided_at = timezone.now()
        request.save()
    return request
