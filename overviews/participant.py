"""Participant detail for coaches (brief 5.10.3, #40).

Levels per topic and suggested next tasks come from the participant's own
catalogue and dashboard services, so the coach sees exactly what the
participant sees. The history covers every submission and hint request,
also for archived or unpublished tasks.
"""

from dataclasses import dataclass

from accounts.models import Profile
from hints.models import HintRequest
from submissions.dashboard import suggested_tasks
from submissions.models import Submission
from tasks.catalogue import CatalogueEntry, TopicSection, catalogue

SUGGESTIONS = 5


@dataclass(frozen=True)
class ParticipantDetail:
    profile: Profile
    sections: list[TopicSection]  # levels per topic
    suggestions: list[CatalogueEntry]
    submissions: list[Submission]  # newest first, drafts left out
    hint_requests: list[HintRequest]  # newest first


def participant_detail(profile: Profile) -> ParticipantDetail:
    user = profile.user
    sections = catalogue(user)
    submissions = list(
        Submission.objects.filter(user=user)
        .exclude(status=Submission.Status.DRAFT)
        .select_related("task__topic", "task_version", "reviewed_by__profile")
        .order_by("-submitted_at", "-pk")
    )
    for submission in submissions:
        if submission.status == Submission.Status.APPROVED:
            submission.points = submission.task_version.base_points * submission.stars
    hint_requests = list(
        HintRequest.objects.filter(task_attempt__user=user)
        .select_related(
            "task_attempt__task__topic", "hint__task_version", "decided_by__profile"
        )
        .order_by("-requested_at", "-pk")
    )
    return ParticipantDetail(
        profile=profile,
        sections=sections,
        suggestions=suggested_tasks(sections, limit=SUGGESTIONS),
        submissions=submissions,
        hint_requests=hint_requests,
    )
