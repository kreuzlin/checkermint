from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Topic(models.Model):
    """A topic such as Code or Konstruktion; levels are per topic (brief 5.3)."""

    name = models.CharField("Name", max_length=50, unique=True)
    slug = models.SlugField(
        "Kurzname für Adressen",
        max_length=50,
        unique=True,
        help_text="Kleinbuchstaben, Ziffern und «-», z. B. «konstruktion».",
    )
    order = models.PositiveSmallIntegerField(
        "Reihenfolge",
        default=0,
        help_text="Kleinere Zahlen stehen weiter vorne.",
    )
    description = models.TextField(
        "Beschreibung",
        blank=True,
        help_text="Kurz, Markdown. Erscheint über den Aufgaben des Themas.",
    )

    class Meta:
        verbose_name = "Thema"
        verbose_name_plural = "Themen"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class LevelThreshold(models.Model):
    """One row of the shared level table for all topics (ADR 0013).

    Level 1 starts at 0 points. Levels are numbered without gaps and the
    points rise strictly with the level.
    """

    level = models.PositiveSmallIntegerField(
        "Level", unique=True, validators=[MinValueValidator(1)]
    )
    min_points = models.PositiveIntegerField(
        "Ab Punkten",
        unique=True,
        help_text="Punkte in einem Thema, ab denen dieses Level erreicht ist.",
    )

    class Meta:
        verbose_name = "Level-Schwelle"
        verbose_name_plural = "Level-Schwellen"
        ordering = ["level"]

    def __str__(self):
        return f"Level {self.level} ab {self.min_points} Punkten"

    def clean(self):
        if self.level is None or self.min_points is None:
            return
        if self.pk:
            old_level = LevelThreshold.objects.get(pk=self.pk).level
            if old_level != self.level:
                raise ValidationError(
                    {"level": "Die Nummer eines Levels lässt sich nicht ändern."}
                )
        if self.level == 1 and self.min_points != 0:
            raise ValidationError(
                {"min_points": "Level 1 beginnt immer bei 0 Punkten."}
            )
        if self.level > 1 and self.min_points == 0:
            raise ValidationError({"min_points": "Nur Level 1 beginnt bei 0 Punkten."})

        others = LevelThreshold.objects.exclude(pk=self.pk)
        if self.level > 1 and not others.filter(level=self.level - 1).exists():
            raise ValidationError(
                {
                    "level": f"Zuerst muss es Level {self.level - 1} geben (keine Lücken)."
                }
            )
        lower = others.filter(level__lt=self.level, min_points__gte=self.min_points)
        higher = others.filter(level__gt=self.level, min_points__lte=self.min_points)
        if lower.exists() or higher.exists():
            raise ValidationError(
                {
                    "min_points": (
                        "Höhere Levels brauchen mehr Punkte als tiefere. "
                        "Prüfe die Nachbar-Levels."
                    )
                }
            )

    def can_be_deleted(self) -> bool:
        """Only the highest level, never level 1 (no gaps, ADR 0013)."""
        if self.level == 1:
            return False
        return not LevelThreshold.objects.filter(level__gt=self.level).exists()
