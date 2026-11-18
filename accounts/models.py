import secrets

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower


def new_avatar_seed() -> str:
    """Random seed for the robot avatar (ADR 0012); no personal data."""
    return secrets.token_hex(8)


nickname_validator = RegexValidator(
    regex=r"^[^\W_][\w-]{1,29}$",
    message=(
        "2 bis 30 Zeichen: Buchstaben, Ziffern, «-» und «_», "
        "am Anfang ein Buchstabe oder eine Ziffer, keine Leerzeichen."
    ),
)


class Profile(models.Model):
    """Platform data of a user (brief, sections 4 and 5.1).

    Only nickname, avatar, points and levels are ever public; the visibility
    flags control what else appears on the public profile page. The real
    name and the email address (on the user) are never public.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Benutzer",
    )
    nickname = models.CharField(
        "Spitzname",
        max_length=30,
        unique=True,
        validators=[nickname_validator],
        help_text=(
            "Öffentlich sichtbar, auch in der Adresse des Profils "
            "(/p/spitzname/). Kein echter Name."
        ),
    )
    real_name = models.CharField(
        "Echter Name",
        max_length=100,
        help_text="Nur für angemeldete Benutzer sichtbar, nie öffentlich.",
    )
    avatar_seed = models.CharField(
        "Avatar-Seed",
        max_length=32,
        default=new_avatar_seed,
        help_text="Bestimmt den Roboter-Avatar. Wird beim Würfeln neu gesetzt.",
    )
    about = models.TextField(
        "Über mich",
        blank=True,
        help_text="Kurzer Text, Markdown. Öffentlich nur, wenn freigegeben.",
    )

    # Visibility on the public profile page (default: private, brief 4.6).
    show_badges = models.BooleanField("Badges öffentlich zeigen", default=False)
    show_about = models.BooleanField("«Über mich» öffentlich zeigen", default=False)
    show_solved_tasks = models.BooleanField(
        "Gelöste Aufgaben öffentlich zeigen",
        default=False,
        help_text="Nur die Titel, nie den Inhalt der Einreichungen.",
    )

    email_notifications = models.BooleanField(
        "E-Mail-Benachrichtigungen",
        default=True,
        help_text=(
            "Nur wirksam, wenn eine E-Mail-Adresse hinterlegt ist. Coaches: "
            "neue Einreichungen und Hinweis-Anfragen. Teilnehmende: Reviews "
            "und Antworten auf Hinweis-Anfragen."
        ),
    )

    created_at = models.DateTimeField("Erstellt", auto_now_add=True)
    updated_at = models.DateTimeField("Geändert", auto_now=True)

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profile"
        ordering = [Lower("nickname")]
        constraints = [
            models.UniqueConstraint(
                Lower("nickname"),
                name="accounts_profile_nickname_ci_unique",
                violation_error_message="Dieser Spitzname ist schon vergeben.",
            ),
        ]

    def __str__(self):
        return self.nickname
