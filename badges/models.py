from pathlib import PurePath

from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from core.private_files import RandomUploadPath


def _delete_after_commit(field_file):
    """Remove a stored file once the database change is committed."""
    if field_file:
        storage, name = field_file.storage, field_file.name
        transaction.on_commit(lambda: storage.delete(name))


class Badge(models.Model):
    """A badge that a task can award on its first approval (brief 5.8)."""

    name = models.CharField("Name", max_length=60, unique=True)
    description = models.CharField(
        "Beschreibung",
        max_length=200,
        blank=True,
        help_text="Wofür es den Badge gibt, in einem Satz.",
    )
    # Uploaded by coaches in the admin (ADR 0018): always our own 512 px PNG
    # from badges.images.process_badge_image, never the original upload.
    # Public through badges:image (public profiles) – the only upload that
    # is (ADR 0009 otherwise). Empty: neutral placeholder.
    image_file = models.ImageField(
        "Bild",
        upload_to=RandomUploadPath("badges"),
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField("Erstellt", auto_now_add=True)

    class Meta:
        verbose_name = "Badge"
        verbose_name_plural = "Badges"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def set_image(self, content) -> None:
        """Store a processed image; the old file goes after the commit."""
        # Captures the old name now, before save() replaces it.
        _delete_after_commit(self.image_file)
        self.image_file.save(content.name, content, save=False)

    def remove_image(self) -> None:
        _delete_after_commit(self.image_file)
        self.image_file = ""

    @property
    def image_url(self) -> str | None:
        """Public URL; it changes with every new upload (random file name)."""
        if not self.image_file:
            return None
        stem = PurePath(self.image_file.name).stem
        return reverse("badges:image", args=[self.pk, stem])


@receiver(post_delete, sender=Badge)
def delete_badge_image(sender, instance, **kwargs):
    _delete_after_commit(instance.image_file)


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
