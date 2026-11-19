"""Submissions and their items (brief 5.6, ADR 0010, ADR 0011).

A submission is made against exactly one published task version and keeps
it forever. Its content (the items) can only change while it is a draft;
once submitted, only the review fields change.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.private_files import RandomUploadPath
from tasks.models import Task, TaskRequirement, TaskVersion

MAX_STARS = 3


class SubmissionLockedError(Exception):
    """The content of a submission that is no longer a draft was to change."""

    def __init__(self, message="Eingereichte Lösungen lassen sich nicht mehr ändern."):
        super().__init__(message)


class Submission(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        SUBMITTED = "submitted", "Eingereicht"
        NEEDS_REVISION = "needs_revision", "Überarbeitung nötig"
        APPROVED = "approved", "Angenommen"

    REVIEWED = (Status.NEEDS_REVISION, Status.APPROVED)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Teilnehmer/in",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name="submissions",
        verbose_name="Aufgabe",
    )
    task_version = models.ForeignKey(
        TaskVersion,
        on_delete=models.PROTECT,
        related_name="submissions",
        verbose_name="Version",
    )
    status = models.CharField(
        "Status", max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    stars = models.PositiveSmallIntegerField(
        "Sterne",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(MAX_STARS)],
        help_text="1 bis 3, nur bei angenommenen Lösungen.",
    )
    feedback = models.TextField("Rückmeldung", blank=True, help_text="Markdown.")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Bewertet von",
    )
    created_at = models.DateTimeField("Erstellt", auto_now_add=True)
    submitted_at = models.DateTimeField("Eingereicht am", null=True, blank=True)
    reviewed_at = models.DateTimeField("Bewertet am", null=True, blank=True)

    class Meta:
        verbose_name = "Einreichung"
        verbose_name_plural = "Einreichungen"
        ordering = ["-submitted_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "task"], name="submission_user_task"),
            models.Index(fields=["status", "submitted_at"], name="submission_queue"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "task"],
                condition=Q(status="draft"),
                name="submissions_one_draft_per_user_task",
                violation_error_message="Für diese Aufgabe gibt es schon einen Entwurf.",
            ),
            models.CheckConstraint(
                condition=Q(stars__isnull=True) | Q(stars__gte=1, stars__lte=MAX_STARS),
                name="submissions_stars_range",
            ),
            # Stars only on approved submissions; "needs revision" is
            # feedback only (brief 5.8).
            models.CheckConstraint(
                condition=Q(status="approved", stars__isnull=False)
                | (~Q(status="approved") & Q(stars__isnull=True)),
                name="submissions_stars_iff_approved",
            ),
            models.CheckConstraint(
                condition=Q(status="draft", submitted_at__isnull=True)
                | (~Q(status="draft") & Q(submitted_at__isnull=False)),
                name="submissions_submitted_at_matches_status",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=["needs_revision", "approved"],
                    reviewed_at__isnull=False,
                )
                | (Q(status__in=["draft", "submitted"]) & Q(reviewed_at__isnull=True)),
                name="submissions_reviewed_at_matches_status",
            ),
        ]

    def __str__(self):
        return f"{self.user} – {self.task_version} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Checked on every save: the version is fixed at creation and is
        # always a published version of the submission's task (ADR 0010).
        if self.pk is not None:
            stored = (
                Submission.objects.filter(pk=self.pk)
                .values_list("user_id", "task_id", "task_version_id")
                .first()
            )
            if stored and stored != (self.user_id, self.task_id, self.task_version_id):
                raise ValueError("User, task and version of a submission never change.")
        version = TaskVersion.objects.filter(pk=self.task_version_id).first()
        if version is None or version.task_id != self.task_id:
            raise ValueError("The version must belong to the submission's task.")
        if not version.is_published:
            raise ValueError("A submission can only use a published version.")
        super().save(*args, **kwargs)

    @property
    def is_draft(self) -> bool:
        return self.status == self.Status.DRAFT

    def stored_is_draft(self) -> bool:
        """Whether the row in the database is a draft (ignores changes in memory)."""
        if self.pk is None:
            return True
        return Submission.objects.filter(pk=self.pk, status=self.Status.DRAFT).exists()

    def clean(self):
        if self.status == self.Status.APPROVED and self.stars is None:
            raise ValidationError({"stars": "Eine angenommene Lösung braucht Sterne."})
        if self.status != self.Status.APPROVED and self.stars is not None:
            raise ValidationError(
                {"stars": "Sterne gibt es nur bei angenommenen Lösungen."}
            )


class SubmissionItemQuerySet(models.QuerySet):
    """Bulk changes must not bypass the draft-only rule."""

    def touches_locked(self) -> bool:
        return self.exclude(submission__status=Submission.Status.DRAFT).exists()

    def update(self, **kwargs):
        if self.touches_locked():
            raise SubmissionLockedError()
        return super().update(**kwargs)

    def delete(self):
        if self.touches_locked():
            raise SubmissionLockedError()
        return super().delete()

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        ids = {obj.submission_id for obj in objs}
        if Submission.objects.filter(pk__in=ids).exclude(status="draft").exists():
            raise SubmissionLockedError()
        return super().bulk_create(objs, *args, **kwargs)


class SubmissionItem(models.Model):
    """One value of a submission: a text, a code snippet, a photo, a file.

    The type is the requirement's type; the handler for that type decides
    which columns it uses (ADR 0011). `data` is for future types only.
    """

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Einreichung",
    )
    requirement = models.ForeignKey(
        TaskRequirement,
        on_delete=models.PROTECT,
        related_name="submission_items",
        verbose_name="Anforderung",
    )
    order = models.PositiveSmallIntegerField("Reihenfolge", default=0)
    text = models.TextField("Text", blank=True)
    file = models.FileField(
        "Datei", upload_to=RandomUploadPath("einreichungen"), blank=True
    )
    original_filename = models.CharField(
        "Ursprünglicher Dateiname", max_length=200, blank=True
    )
    thumbnail = models.FileField(
        "Vorschaubild",
        upload_to=RandomUploadPath("einreichungen/vorschau"),
        blank=True,
    )
    data = models.JSONField("Daten", default=dict, blank=True)
    created_at = models.DateTimeField("Erstellt", auto_now_add=True)

    objects = SubmissionItemQuerySet.as_manager()

    class Meta:
        verbose_name = "Teil einer Einreichung"
        verbose_name_plural = "Teile einer Einreichung"
        ordering = ["submission", "requirement__order", "requirement", "order", "pk"]

    def __str__(self):
        return f"{self.requirement} ({self.order + 1})"

    def save(self, *args, **kwargs):
        submission = Submission.objects.filter(pk=self.submission_id).first()
        if submission is None:
            raise ValueError("An item needs a saved submission.")
        if not submission.is_draft or not self._stored_submission_is_draft():
            raise SubmissionLockedError()
        requirement = TaskRequirement.objects.filter(pk=self.requirement_id).first()
        if (
            requirement is None
            or requirement.task_version_id != submission.task_version_id
        ):
            raise ValueError("The requirement must belong to the submission's version.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self._stored_submission_is_draft():
            raise SubmissionLockedError()
        files = [(f.name, f.storage) for f in (self.file, self.thumbnail) if f]
        result = super().delete(*args, **kwargs)
        for name, storage in files:
            storage.delete(name)
        return result

    def _stored_submission_is_draft(self) -> bool:
        """The submission this row is stored under (it could be moved in memory)."""
        if self.pk is None:
            return True
        return SubmissionItem.objects.filter(
            pk=self.pk, submission__status=Submission.Status.DRAFT
        ).exists()
