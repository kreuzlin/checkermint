"""Awarding badges and reading them back (brief 5.8, 5.9, ADR 0013)."""

from django.db import IntegrityError, transaction

from .models import UserBadge


def award_for(submission) -> UserBadge | None:
    """Give the task's badge for an approved submission, once per user.

    Returns the new award, or None if the task has no badge or the user
    has it already. A badge added to a task later is given on the next
    approval of that task, not retroactively.
    """
    badge_id = submission.task.badge_id
    if badge_id is None or submission.status != "approved":
        return None
    if UserBadge.objects.filter(user=submission.user_id, badge=badge_id).exists():
        return None
    try:
        with transaction.atomic():
            return UserBadge.objects.create(
                user_id=submission.user_id,
                badge_id=badge_id,
                submission=submission,
                awarded_at=submission.reviewed_at,
            )
    except IntegrityError:  # awarded at the same moment by another review
        return None


def with_details(queryset):
    return queryset.select_related("badge", "user__profile", "submission__task_version")


def recent_badges(limit: int = 8):
    """Latest awards across the club, for logged-in users (brief 5.9)."""
    return with_details(UserBadge.objects.filter(user__is_active=True))[:limit]


def badges_of(user):
    return with_details(UserBadge.objects.filter(user=user))
