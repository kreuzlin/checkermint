"""Public profile pages `/p/<nickname>/` (brief 4.6, 5.1, 5.12, #46).

Only what the participant made public: nickname, avatar, points and levels
per topic always; badges, "about me" and the titles of solved tasks only
with the matching switch. Never the real name, the email address or any
submission content. Each optional part is loaded only when its switch is
on, so a private part cannot leak through the template.
"""

from dataclasses import dataclass

from badges.awards import badges_of
from submissions.models import Submission
from submissions.progress import levels_by_topic
from tasks.catalogue import visible_tasks
from tasks.levels import LevelInfo
from tasks.models import Topic

from .models import Profile


@dataclass(frozen=True)
class TopicLevel:
    topic: Topic
    progress: LevelInfo


@dataclass(frozen=True)
class SolvedTask:
    topic: str
    title: str


@dataclass(frozen=True)
class PublicProfile:
    nickname: str
    avatar_seed: str
    levels: list[TopicLevel]
    about: str | None  # None: not public
    badges: list | None  # None: not public
    solved_tasks: list[SolvedTask] | None  # None: not public


def public_profile(profile: Profile) -> PublicProfile:
    user = profile.user
    topics = list(Topic.objects.filter(tasks__in=visible_tasks()).distinct())
    levels = levels_by_topic(user, {topic.pk for topic in topics})
    return PublicProfile(
        nickname=profile.nickname,
        avatar_seed=profile.avatar_seed,
        levels=[TopicLevel(topic, levels[topic.pk]) for topic in topics],
        about=profile.about if profile.show_about else None,
        badges=list(badges_of(user)) if profile.show_badges else None,
        solved_tasks=_solved_tasks(user) if profile.show_solved_tasks else None,
    )


def _solved_tasks(user) -> list[SolvedTask]:
    """Titles of the visible tasks with an approved submission, in
    catalogue order (title of the latest published version)."""
    solved = Submission.objects.filter(
        user=user, status=Submission.Status.APPROVED
    ).values("task_id")
    tasks = visible_tasks().filter(pk__in=solved).select_related("topic")
    result = []
    for task in tasks.order_by("topic__order", "topic__name", "order", "slug"):
        version = task.latest_published_version()
        result.append(SolvedTask(topic=task.topic.name, title=version.title))
    return result
