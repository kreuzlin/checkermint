"""Ranking per topic (brief 5.9, #48): deliberately low-key.

Active participants with points in the topic, most points first; equal
points share a rank (1, 2, 2, 4). Participants without points are not
listed, only counted. Points as everywhere (`submissions.progress`,
ADR 0013), so the ranking agrees with the catalogue and dashboard.
"""

from dataclasses import dataclass

from django.db.models import F, Max

from accounts.models import Profile
from accounts.views import participant_profiles
from tasks.levels import level_for_points, thresholds
from tasks.models import Topic

from .models import Submission


@dataclass(frozen=True)
class RankingRow:
    rank: int
    profile: Profile
    points: int
    level: int


@dataclass(frozen=True)
class Ranking:
    topic: Topic
    rows: list[RankingRow]
    without_points: int  # active participants not listed


def topic_ranking(topic: Topic) -> Ranking:
    profiles = {p.user_id: p for p in participant_profiles()}
    points: dict[int, int] = {}
    rows = (
        Submission.objects.filter(
            status=Submission.Status.APPROVED, task__topic=topic, user__in=profiles
        )
        .values("user_id", "task_id")
        .annotate(best=Max(F("task_version__base_points") * F("stars")))
        .values_list("user_id", "best")
    )
    for user_id, best in rows:
        points[user_id] = points.get(user_id, 0) + best
    ordered = sorted(
        points.items(), key=lambda item: (-item[1], profiles[item[0]].nickname.lower())
    )
    table = thresholds()
    result: list[RankingRow] = []
    for position, (user_id, total) in enumerate(ordered, start=1):
        tied = result and result[-1].points == total
        result.append(
            RankingRow(
                rank=result[-1].rank if tied else position,
                profile=profiles[user_id],
                points=total,
                level=level_for_points(total, table).level,
            )
        )
    return Ranking(topic=topic, rows=result, without_points=len(profiles) - len(result))
