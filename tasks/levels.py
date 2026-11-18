"""Level from points with the shared threshold table (ADR 0013)."""

from dataclasses import dataclass

from .models import LevelThreshold


@dataclass(frozen=True)
class LevelInfo:
    level: int
    points: int
    next_level_points: int | None  # None at the highest level

    @property
    def points_missing(self) -> int | None:
        if self.next_level_points is None:
            return None
        return self.next_level_points - self.points


def thresholds() -> list[tuple[int, int]]:
    """(level, min_points) pairs, lowest level first."""
    return list(
        LevelThreshold.objects.order_by("level").values_list("level", "min_points")
    )


def level_for_points(
    points: int, table: list[tuple[int, int]] | None = None
) -> LevelInfo:
    """Highest level whose `min_points` is reached, plus the next threshold."""
    table = thresholds() if table is None else table
    level, next_points = 1, None
    for threshold_level, min_points in table:
        if points >= min_points:
            level = threshold_level
        else:
            next_points = min_points
            break
    return LevelInfo(level=level, points=points, next_level_points=next_points)
