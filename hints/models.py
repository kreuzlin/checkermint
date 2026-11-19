from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

MESSAGE_MAX_LENGTH = 300


class HintRequest(models.Model):
    """A participant asks for the next hint of a task (brief 5.5).

    Hints are not self-service: a coach grants or declines the request
    (#37). Every request and decision is kept. A hint counts as granted for
    the attempt if a granted request exists for a hint with the same key, so
    granted hints stay granted after a version switch (brief 5.5, #38).
    """

    class Status(models.TextChoices):
        OPEN = "open", "Offen"
        GRANTED = "granted", "Freigegeben"
        DECLINED = "declined", "Abgelehnt"

    task_attempt = models.ForeignKey(
        "tasks.TaskAttempt",
        on_delete=models.CASCADE,
        related_name="hint_requests",
        verbose_name="Aufgaben-Versuch",
    )
    hint = models.ForeignKey(
        "tasks.Hint",
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="Hinweis",
    )
    message = models.CharField("Nachricht", max_length=MESSAGE_MAX_LENGTH, blank=True)
    status = models.CharField(
        "Status", max_length=20, choices=Status.choices, default=Status.OPEN
    )
    coach_reply = models.CharField(
        "Antwort des Coachs", max_length=MESSAGE_MAX_LENGTH, blank=True
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Entschieden von",
    )
    requested_at = models.DateTimeField("Angefragt am", default=timezone.now)
    decided_at = models.DateTimeField("Entschieden am", null=True, blank=True)

    class Meta:
        verbose_name = "Hinweis-Anfrage"
        verbose_name_plural = "Hinweis-Anfragen"
        ordering = ["-requested_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_attempt"],
                condition=Q(status="open"),
                name="hints_one_open_request_per_attempt",
                violation_error_message="Es wartet schon eine Anfrage auf einen Coach.",
            ),
            models.CheckConstraint(
                condition=Q(status="open", decided_at__isnull=True)
                | (~Q(status="open") & Q(decided_at__isnull=False)),
                name="hints_decided_at_iff_decided",
                violation_error_message="Entschiedene Anfragen brauchen ein Datum.",
            ),
        ]
        indexes = [models.Index(fields=["status", "requested_at"])]

    def __str__(self):
        return f"{self.hint} – {self.task_attempt.user}"

    @property
    def user(self):
        return self.task_attempt.user

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN
