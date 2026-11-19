from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.templatetags.static import static
from django.utils import timezone

# Badge artwork is a static asset, not an upload: it can appear on public
# profiles, and uploads are always private (brief 4.2, ADR 0009). Original
# files go to design/ (issue #4); the web versions live here.
IMAGE_DIR = Path(__file__).resolve().parent / "static" / "badges" / "img"
IMAGE_EXTENSIONS = {".svg", ".png", ".webp"}


def available_images() -> list[str]:
    """File names of the badge images that ship with the app."""
    if not IMAGE_DIR.is_dir():
        return []
    return sorted(
        path.name
        for path in IMAGE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


class Badge(models.Model):
    """A badge that a task can award on its first approval (brief 5.8)."""

    name = models.CharField("Name", max_length=60, unique=True)
    description = models.CharField(
        "Beschreibung",
        max_length=200,
        blank=True,
        help_text="Wofür es den Badge gibt, in einem Satz.",
    )
    image = models.CharField(
        "Bild",
        max_length=100,
        blank=True,
        help_text=(
            "Eines der Badge-Bilder, die mit der Website ausgeliefert werden. "
            "Leer: neutraler Platzhalter."
        ),
    )
    created_at = models.DateTimeField("Erstellt", auto_now_add=True)

    class Meta:
        verbose_name = "Badge"
        verbose_name_plural = "Badges"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.image and self.image not in available_images():
            raise ValidationError({"image": "Dieses Bild gibt es nicht."})

    @property
    def image_url(self) -> str | None:
        if not self.image:
            return None
        return static(f"badges/img/{self.image}")


class UserBadge(models.Model):
    """A badge a participant has received (brief 5.8, ADR 0013).

    Stored, not derived: it is an event with a date. Awarded once per user
    and badge, on the approval of a task that has the badge
    (`badges.awards.award_for`). Revoking means deleting the row in the admin.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
        verbose_name="Teilnehmer/in",
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.PROTECT,
        related_name="awards",
        verbose_name="Badge",
    )
    submission = models.ForeignKey(
        "submissions.Submission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="badge_awards",
        verbose_name="Für die Einreichung",
    )
    awarded_at = models.DateTimeField("Vergeben am", default=timezone.now)

    class Meta:
        verbose_name = "Vergebener Badge"
        verbose_name_plural = "Vergebene Badges"
        ordering = ["-awarded_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "badge"],
                name="badges_userbadge_once_per_user",
                violation_error_message="Diesen Badge hat die Person schon.",
            ),
        ]
        indexes = [models.Index(fields=["-awarded_at"], name="userbadge_recent")]

    def __str__(self):
        return f"{self.badge} – {self.user}"
