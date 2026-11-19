"""Email notifications (brief 5.11, #43, #44).

Mails are sent after the surrounding transaction commits, one message per
recipient (nobody sees the other addresses). A failing mail server never
breaks the action that triggered the mail: the error is logged.

Links are absolute, built from the request that triggered the mail, so no
extra setting for the site address is needed.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import get_connection, send_mass_mail
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME

logger = logging.getLogger(__name__)


def coach_recipients() -> list[str]:
    """Email addresses of active coaches (and superusers) who have an
    address and did not turn notifications off in their profile."""
    User = get_user_model()
    users = (
        User.objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(is_staff=True, groups__name=COACH_GROUP_NAME))
        .exclude(email="")
        .exclude(profile__email_notifications=False)
        .distinct()
        .order_by("pk")
    )
    return [user.email for user in users]


def nickname(user) -> str:
    profile = getattr(user, "profile", None)
    return profile.nickname if profile else user.get_username()


def send_after_commit(template: str, context: dict, recipients: list[str]) -> None:
    """Render `<template>_subject.txt` / `_body.txt` and send after commit."""
    if not recipients:
        return
    context = {
        "site_name": settings.SITE_SHORT_NAME,
        "site_full_name": settings.SITE_NAME,
        **context,
    }
    base = f"notifications/email/{template}"
    subject = " ".join(render_to_string(f"{base}_subject.txt", context).split())
    body = render_to_string(f"{base}_body.txt", context)

    def send():
        messages = [
            (subject, body, settings.DEFAULT_FROM_EMAIL, [address])
            for address in recipients
        ]
        try:
            send_mass_mail(messages, connection=get_connection())
        except Exception:
            logger.exception("Sending %s notification failed", template)

    transaction.on_commit(send)


def notify_coaches_of_submission(request, submission, resubmission: bool) -> None:
    """A solution was submitted or resubmitted (brief 5.11)."""
    send_after_commit(
        "coach_submission",
        {
            "nickname": nickname(submission.user),
            "title": submission.task_version.title,
            "topic": submission.task.topic.name,
            "resubmission": resubmission,
            "url": request.build_absolute_uri(
                reverse("submissions:review", kwargs={"pk": submission.pk})
            ),
            "profile_url": request.build_absolute_uri(reverse("accounts:profile_edit")),
        },
        coach_recipients(),
    )


def notify_coaches_of_hint_request(request, hint_request) -> None:
    """A participant asked for a hint (brief 5.11)."""
    attempt = hint_request.task_attempt
    send_after_commit(
        "coach_hint_request",
        {
            "nickname": nickname(attempt.user),
            "title": hint_request.hint.task_version.title,
            "topic": attempt.task.topic.name,
            "message": hint_request.message,
            "url": request.build_absolute_uri(reverse("submissions:queue")),
            "profile_url": request.build_absolute_uri(reverse("accounts:profile_edit")),
        },
        coach_recipients(),
    )


def participant_recipient(user) -> list[str]:
    """The participant's address, if active, with an address and the
    switch on (brief 5.11: only participants with an email address)."""
    profile = getattr(user, "profile", None)
    if not user.is_active or not user.email:
        return []
    if profile is not None and not profile.email_notifications:
        return []
    return [user.email]


def notify_participant_of_review(request, submission) -> None:
    """A coach approved the solution or asked for a revision (#44)."""
    award = submission.badge_awards.select_related("badge").first()
    send_after_commit(
        "participant_review",
        {
            "nickname": nickname(submission.user),
            "title": submission.task_version.title,
            "approved": submission.status == submission.Status.APPROVED,
            "stars": submission.stars,
            "points": (
                submission.task_version.base_points * submission.stars
                if submission.stars
                else None
            ),
            "feedback": submission.feedback,
            "badge": award.badge.name if award else "",
            "url": request.build_absolute_uri(
                reverse("tasks:task_detail", kwargs={"slug": submission.task.slug})
            ),
            "profile_url": request.build_absolute_uri(reverse("accounts:profile_edit")),
        },
        participant_recipient(submission.user),
    )


def notify_participant_of_hint_decision(request, hint_request) -> None:
    """A coach granted or declined the hint request (#44)."""
    attempt = hint_request.task_attempt
    send_after_commit(
        "participant_hint_decision",
        {
            "nickname": nickname(attempt.user),
            "title": hint_request.hint.task_version.title,
            "granted": hint_request.status == hint_request.Status.GRANTED,
            "reply": hint_request.coach_reply,
            "url": request.build_absolute_uri(
                reverse("tasks:task_detail", kwargs={"slug": attempt.task.slug})
            ),
            "profile_url": request.build_absolute_uri(reverse("accounts:profile_edit")),
        },
        participant_recipient(attempt.user),
    )
