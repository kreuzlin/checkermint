import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.roles import is_coach
from core.private_files import RandomUploadPath


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


# --- Tasks and immutable versions (ADR 0010, 0011) ------------------------


class PublishedVersionError(Exception):
    """A published task version, its requirements or hints were to change.

    Published versions are immutable (brief 5.4, ADR 0010): any change means
    a new version.
    """

    def __init__(self, message="Veröffentlichte Versionen lassen sich nicht ändern."):
        super().__init__(message)


def protect_published_versions(collector, field, sub_objs, using):
    """`on_delete` for TaskVersion.task: drafts go, published versions stay.

    Cascading deletes bypass `Model.delete()` and `QuerySet.delete()`, so
    deleting a task must be stopped here.
    """
    published = [v for v in sub_objs if v.status == TaskVersion.Status.PUBLISHED]
    if published:
        raise models.ProtectedError(
            "Aufgaben mit veröffentlichten Versionen lassen sich nicht löschen; "
            "archiviere sie stattdessen.",
            set(published),
        )
    models.CASCADE(collector, field, sub_objs, using)


class Task(models.Model):
    """The stable part of a task (brief 5.3); content lives in versions."""

    topic = models.ForeignKey(
        Topic, on_delete=models.PROTECT, related_name="tasks", verbose_name="Thema"
    )
    slug = models.SlugField(
        "Kurzname für Adressen",
        max_length=60,
        unique=True,
        help_text="Bleibt fest, auch wenn sich der Titel in einer neuen Version ändert.",
    )
    order = models.PositiveSmallIntegerField(
        "Reihenfolge", default=0, help_text="Innerhalb des Themas, kleinere zuerst."
    )
    min_level = models.PositiveSmallIntegerField(
        "Ab Level",
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Gesperrt, bis das Level in diesem Thema erreicht ist.",
    )
    badge = models.ForeignKey(
        "badges.Badge",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name="Badge",
        help_text="Wird bei der ersten Annahme einer Lösung vergeben.",
    )
    is_published = models.BooleanField(
        "Für Teilnehmende sichtbar",
        default=False,
        help_text="Braucht eine veröffentlichte Version.",
    )
    is_archived = models.BooleanField(
        "Archiviert",
        default=False,
        help_text="Nicht mehr im Katalog; Punkte und Verlauf bleiben.",
    )
    created_at = models.DateTimeField("Erstellt", auto_now_add=True)

    class Meta:
        verbose_name = "Aufgabe"
        verbose_name_plural = "Aufgaben"
        ordering = ["topic__order", "topic__name", "order", "slug"]

    def __str__(self):
        version = self.latest_published_version()
        return version.title if version else self.slug

    def latest_published_version(self):
        return self.versions.published().order_by("-number").first()

    def draft_version(self):
        return self.versions.drafts().first()

    def create_draft(self, user=None):
        """ "Neue Version erstellen" (brief 5.4, ADR 0010).

        Copies the latest published version with its requirements and hints
        (keys kept) into a new draft. Without any version, an empty draft is
        created. Returns the existing draft if there is one.
        """
        with transaction.atomic():
            # Lock the task so two coaches cannot create two drafts at once.
            Task.objects.select_for_update().get(pk=self.pk)
            draft = self.draft_version()
            if draft:
                return draft
            source = self.latest_published_version()
            if source is None:
                return TaskVersion.objects.create(
                    task=self, title=self.slug, instructions="", created_by=user
                )
            draft = TaskVersion.objects.create(
                task=self,
                title=source.title,
                instructions=source.instructions,
                base_points=source.base_points,
                created_by=user,
            )
            TaskRequirement.objects.bulk_create(
                TaskRequirement(
                    task_version=draft,
                    key=r.key,
                    order=r.order,
                    type=r.type,
                    label=r.label,
                    help_text=r.help_text,
                    required=r.required,
                    min_count=r.min_count,
                    max_count=r.max_count,
                    options=r.options,
                )
                for r in source.requirements.all()
            )
            Hint.objects.bulk_create(
                Hint(task_version=draft, key=h.key, order=h.order, text=h.text)
                for h in source.hints.all()
            )
            return draft

    def clean(self):
        if self.is_published and (
            not self.pk or not self.versions.published().exists()
        ):
            raise ValidationError(
                {"is_published": ("Zuerst muss es eine veröffentlichte Version geben.")}
            )


class TaskVersionQuerySet(models.QuerySet):
    """Bulk operations must not bypass the immutability guard."""

    def published(self):
        return self.filter(status=TaskVersion.Status.PUBLISHED)

    def drafts(self):
        return self.filter(status=TaskVersion.Status.DRAFT)

    def update(self, **kwargs):
        if self.published().exists():
            raise PublishedVersionError()
        return super().update(**kwargs)

    def delete(self):
        if self.published().exists():
            raise PublishedVersionError()
        return super().delete()


class TaskVersion(models.Model):
    """What participants read and fulfil; immutable once published."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        PUBLISHED = "published", "Veröffentlicht"

    task = models.ForeignKey(
        Task,
        on_delete=protect_published_versions,
        related_name="versions",
        verbose_name="Aufgabe",
    )
    number = models.PositiveSmallIntegerField("Version", editable=False)
    status = models.CharField(
        "Status", max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    title = models.CharField("Titel", max_length=120)
    instructions = models.TextField(
        "Anleitung", help_text="Markdown. Bilder folgen mit einer späteren Version."
    )
    base_points = models.PositiveSmallIntegerField(
        "Grundpunkte",
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Punkte = Grundpunkte × Sterne (1 bis 3).",
    )
    change_note = models.CharField(
        "Änderungsnotiz",
        max_length=200,
        blank=True,
        help_text="Was ist neu? Teilnehmende sehen das beim Wechsel.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Erstellt von",
    )
    created_at = models.DateTimeField("Erstellt", auto_now_add=True)
    published_at = models.DateTimeField("Veröffentlicht am", null=True, blank=True)

    objects = TaskVersionQuerySet.as_manager()

    class Meta:
        verbose_name = "Aufgaben-Version"
        verbose_name_plural = "Aufgaben-Versionen"
        ordering = ["task", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "number"], name="tasks_version_unique_number"
            ),
            models.UniqueConstraint(
                fields=["task"],
                condition=Q(status="draft"),
                name="tasks_version_one_draft_per_task",
                violation_error_message="Diese Aufgabe hat schon einen Entwurf.",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="draft", published_at__isnull=True)
                    | Q(status="published", published_at__isnull=False)
                ),
                name="tasks_version_published_at_matches_status",
            ),
        ]

    def __str__(self):
        return f"{self.title} (Version {self.number})"

    def save(self, *args, **kwargs):
        # Allowed: creating a draft, changing a draft, and draft → published.
        if self.stored_is_published():
            raise PublishedVersionError()
        if self.number is None:
            last = TaskVersion.objects.filter(task=self.task_id).aggregate(
                models.Max("number")
            )["number__max"]
            self.number = (last or 0) + 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.stored_is_published():
            raise PublishedVersionError()
        return super().delete(*args, **kwargs)

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    def stored_is_published(self) -> bool:
        """Whether the row in the database is published (ignores changes in memory)."""
        if self.pk is None:
            return False
        return TaskVersion.objects.published().filter(pk=self.pk).exists()

    def publish(self):
        """Draft → published, the only allowed change of a version's state."""
        if self.stored_is_published():
            raise PublishedVersionError("Diese Version ist schon veröffentlicht.")
        if not self.requirements.exists():
            raise ValidationError(
                "Eine Version braucht mindestens eine Anforderung (was eingereicht wird)."
            )
        with transaction.atomic():
            self.status = self.Status.PUBLISHED
            self.published_at = timezone.now()
            self.save()


class VersionChildQuerySet(models.QuerySet):
    """Requirements and hints of published versions are immutable too."""

    def touches_published(self) -> bool:
        return self.filter(task_version__status=TaskVersion.Status.PUBLISHED).exists()

    def update(self, **kwargs):
        if self.touches_published():
            raise PublishedVersionError()
        return super().update(**kwargs)

    def delete(self):
        if self.touches_published():
            raise PublishedVersionError()
        return super().delete()

    def bulk_create(self, objs, *args, **kwargs):
        objs = list(objs)
        version_ids = {obj.task_version_id for obj in objs}
        if TaskVersion.objects.published().filter(pk__in=version_ids).exists():
            raise PublishedVersionError()
        return super().bulk_create(objs, *args, **kwargs)


class VersionChild(models.Model):
    """Base for rows that belong to a task version (requirements, hints)."""

    key = models.SlugField(
        "Schlüssel",
        max_length=50,
        help_text=(
            "Fester Kurzname, bleibt in neuen Versionen gleich (verbindet "
            "Entwürfe und Hinweise über Versionen hinweg)."
        ),
    )
    order = models.PositiveSmallIntegerField("Reihenfolge", default=0)

    objects = VersionChildQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self._version_is_published() or self._stored_version_is_published():
            raise PublishedVersionError()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._stored_version_is_published():
            raise PublishedVersionError()
        return super().delete(*args, **kwargs)

    def _version_is_published(self) -> bool:
        return TaskVersion.objects.published().filter(pk=self.task_version_id).exists()

    def _stored_version_is_published(self) -> bool:
        """The version this row is stored under (it could be moved in memory)."""
        if self.pk is None:
            return False
        stored = (
            type(self)
            .objects.filter(pk=self.pk)
            .values_list("task_version__status", flat=True)
        )
        return TaskVersion.Status.PUBLISHED in stored


class TaskRequirement(VersionChild):
    """What a submission must contain (ADR 0011)."""

    class Type(models.TextChoices):
        TEXT = "text", "Text"
        CODE = "code", "Code"
        PHOTO = "photo", "Foto"
        FILE = "file", "Datei"

    task_version = models.ForeignKey(
        TaskVersion,
        on_delete=models.CASCADE,
        related_name="requirements",
        verbose_name="Version",
    )
    type = models.CharField("Art", max_length=20, choices=Type.choices)
    label = models.CharField("Bezeichnung", max_length=100)
    help_text = models.CharField("Hilfetext", max_length=300, blank=True)
    required = models.BooleanField("Pflicht", default=True)
    min_count = models.PositiveSmallIntegerField(
        "Mindestens", default=1, help_text="z. B. 2 Fotos"
    )
    max_count = models.PositiveSmallIntegerField(
        "Höchstens", default=1, validators=[MinValueValidator(1)]
    )
    options = models.JSONField(
        "Optionen",
        default=dict,
        blank=True,
        help_text="Für Fachleute: Einstellungen je Art, z. B. erlaubte Dateiendungen.",
    )

    class Meta:
        verbose_name = "Anforderung"
        verbose_name_plural = "Anforderungen"
        ordering = ["task_version", "order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_version", "key"],
                name="tasks_requirement_unique_key",
                violation_error_message="Dieser Schlüssel kommt in der Version schon vor.",
            ),
            models.CheckConstraint(
                condition=Q(min_count__lte=models.F("max_count")),
                name="tasks_requirement_min_lte_max",
                violation_error_message="«Mindestens» darf nicht grösser sein als «Höchstens».",
            ),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        if self.required and self.min_count < 1:
            raise ValidationError(
                {"min_count": "Bei einer Pflicht-Anforderung mindestens 1."}
            )
        if not isinstance(self.options, dict):
            raise ValidationError({"options": "Optionen müssen ein Objekt sein: {…}."})


class Hint(VersionChild):
    """A hint that a coach can grant on request (brief 5.5)."""

    task_version = models.ForeignKey(
        TaskVersion,
        on_delete=models.CASCADE,
        related_name="hints",
        verbose_name="Version",
    )
    text = models.TextField("Hinweis", help_text="Markdown.")

    class Meta:
        verbose_name = "Hinweis"
        verbose_name_plural = "Hinweise"
        ordering = ["task_version", "order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_version", "key"],
                name="tasks_hint_unique_key",
                violation_error_message="Dieser Schlüssel kommt in der Version schon vor.",
            ),
        ]

    def __str__(self):
        return f"Hinweis {self.key}"


# --- Images in instructions (brief 5.4, ADR 0010, ADR 0009) ---------------

IMAGE_REFERENCE = re.compile(r"\(bild:(\d+)\)")


def referenced_image_ids(text: str) -> set[int]:
    """Ids of images referenced as ![…](bild:12) in Markdown."""
    return {int(match) for match in IMAGE_REFERENCE.findall(text or "")}


class InstructionImage(models.Model):
    """An image for the instructions of a task, shared by its versions.

    Stored privately (ADR 0009) and re-encoded without metadata. Once
    saved it is never replaced; it cannot be deleted while a published
    version references it, so old versions keep rendering (ADR 0010).
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="instruction_images",
        verbose_name="Aufgabe",
    )
    image = models.ImageField(
        "Bild",
        upload_to=RandomUploadPath("anleitungen"),
        width_field="width",
        height_field="height",
    )
    width = models.PositiveIntegerField(editable=False, null=True)
    height = models.PositiveIntegerField(editable=False, null=True)
    alt_text = models.CharField(
        "Alternativtext",
        max_length=200,
        help_text="Was ist auf dem Bild zu sehen? Für Screenreader und falls das Bild fehlt.",
    )
    original_filename = models.CharField(
        "Ursprünglicher Dateiname", max_length=200, blank=True, editable=False
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Hochgeladen von",
    )
    created_at = models.DateTimeField("Hochgeladen", auto_now_add=True)

    class Meta:
        verbose_name = "Bild in der Anleitung"
        verbose_name_plural = "Bilder in der Anleitung"
        ordering = ["task", "pk"]

    def __str__(self):
        return self.alt_text

    def save(self, *args, **kwargs):
        if self.pk is not None:
            stored = InstructionImage.objects.filter(pk=self.pk).values_list(
                "image", "task_id"
            )
            if stored and stored[0] != (self.image.name, self.task_id):
                raise PublishedVersionError(
                    "Ein hochgeladenes Bild lässt sich nicht ersetzen; lade ein neues hoch."
                )
            if self.used_by_published_version():
                raise PublishedVersionError()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.used_by_published_version():
            raise PublishedVersionError(
                "Dieses Bild wird von einer veröffentlichten Version verwendet."
            )
        name, storage = self.image.name, self.image.storage
        result = super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
        return result

    @property
    def reference(self) -> str:
        """Markdown to paste into the instructions."""
        return f"![{self.alt_text}](bild:{self.pk})"

    def versions_using(self):
        return [
            version
            for version in self.task.versions.all()
            if self.pk in referenced_image_ids(version.instructions)
        ]

    def used_by_published_version(self) -> bool:
        if self.pk is None:
            return False
        return any(
            self.pk in referenced_image_ids(text)
            for text in self.task.versions.published().values_list(
                "instructions", flat=True
            )
        )

    def visible_to(self, user) -> bool:
        """Coaches always; other logged-in users if a published version of a
        visible task shows it (ADR 0009)."""
        if not user.is_authenticated:
            return False
        if is_coach(user):
            return True
        return (
            self.task.is_published
            and not self.task.is_archived
            and self.used_by_published_version()
        )


# --- Task attempts: the pinned version per participant (brief 5.4) --------


class TaskAttempt(models.Model):
    """A participant has started a task; pins the version they see (ADR 0010).

    Created on the first of "Aufgabe starten", the first draft submission or
    the first hint request (see `tasks.attempts.start_attempt`). The version
    changes only when the participant switches explicitly (#26).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_attempts",
        verbose_name="Teilnehmer/in",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name="attempts",
        verbose_name="Aufgabe",
    )
    task_version = models.ForeignKey(
        TaskVersion,
        on_delete=models.PROTECT,
        related_name="attempts",
        verbose_name="Version",
    )
    started_at = models.DateTimeField("Gestartet", default=timezone.now)
    switched_at = models.DateTimeField(
        "Zuletzt Version gewechselt", null=True, blank=True
    )

    class Meta:
        verbose_name = "Aufgaben-Versuch"
        verbose_name_plural = "Aufgaben-Versuche"
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "task"],
                name="tasks_attempt_unique_user_task",
                violation_error_message="Diese Aufgabe ist schon gestartet.",
            ),
        ]

    def __str__(self):
        return f"{self.user} – {self.task_version}"

    def save(self, *args, **kwargs):
        # Checked on every save, not only in forms: an attempt must never
        # pin a draft or a version of another task.
        version = TaskVersion.objects.filter(pk=self.task_version_id).first()
        if version is None or version.task_id != self.task_id:
            raise ValueError("The version must belong to the attempt's task.")
        if not version.is_published:
            raise ValueError("An attempt can only pin a published version.")
        super().save(*args, **kwargs)

    def clean(self):
        version = self.task_version
        if version is None:
            return
        if version.task_id != self.task_id:
            raise ValidationError(
                {"task_version": "Die Version gehört zu einer anderen Aufgabe."}
            )
        if not version.is_published:
            raise ValidationError(
                {"task_version": "Nur veröffentlichte Versionen lassen sich starten."}
            )
