"""Tasks with immutable versions, requirements and hints (ADR 0010/0011, #16)."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase

from badges.models import Badge
from tasks.models import (
    Hint,
    PublishedVersionError,
    Task,
    TaskRequirement,
    TaskVersion,
    Topic,
)


def make_task(slug="linienfolger", **fields):
    topic, _ = Topic.objects.get_or_create(name="Code", slug="code")
    return Task.objects.create(topic=topic, slug=slug, **fields)


def make_version(task, title="Linienfolger", with_children=True):
    version = TaskVersion.objects.create(
        task=task, title=title, instructions="Baue einen **Linienfolger**."
    )
    if with_children:
        TaskRequirement.objects.create(
            task_version=version, key="erklaerung", type="text", label="Erklärung"
        )
        TaskRequirement.objects.create(
            task_version=version,
            key="fotos",
            type="photo",
            label="Fotos",
            min_count=2,
            max_count=5,
            order=1,
        )
        Hint.objects.create(
            task_version=version, key="sensor", text="Prüfe den Sensor."
        )
    return version


class VersionNumberingTests(TestCase):
    def test_numbers_count_up_per_task(self):
        task = make_task()
        first = make_version(task)
        first.publish()
        second = make_version(task)
        other = make_version(make_task("andere"))
        self.assertEqual((first.number, second.number, other.number), (1, 2, 1))

    def test_only_one_draft_per_task(self):
        task = make_task()
        make_version(task)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_version(task, with_children=False)

    def test_latest_published_version_and_str(self):
        task = make_task()
        self.assertEqual(str(task), "linienfolger")
        first = make_version(task, title="Alt")
        first.publish()
        make_version(task, title="Entwurf")
        self.assertEqual(task.latest_published_version(), first)
        self.assertEqual(str(task), "Alt")


class PublishTests(TestCase):
    def test_publish_sets_status_and_date(self):
        version = make_version(make_task())
        version.publish()
        version.refresh_from_db()
        self.assertTrue(version.is_published)
        self.assertIsNotNone(version.published_at)

    def test_publish_needs_a_requirement(self):
        version = make_version(make_task(), with_children=False)
        with self.assertRaisesMessage(ValidationError, "mindestens eine Anforderung"):
            version.publish()

    def test_cannot_publish_twice(self):
        version = make_version(make_task())
        version.publish()
        with self.assertRaises(PublishedVersionError):
            version.publish()

    def test_status_and_published_at_must_match(self):
        version = make_version(make_task())
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskVersion.objects.filter(pk=version.pk).update(status="published")


class PublishedVersionGuardTests(TestCase):
    """The guards work in the model layer, independent of the admin."""

    def setUp(self):
        self.task = make_task()
        self.version = make_version(self.task)
        self.version.publish()
        self.requirement = self.version.requirements.get(key="erklaerung")
        self.hint = self.version.hints.get()

    def test_version_save_is_refused(self):
        self.version.title = "Tippfehler korrigiert"
        with self.assertRaises(PublishedVersionError):
            self.version.save()
        self.version.refresh_from_db()
        self.assertEqual(self.version.title, "Linienfolger")

    def test_reverting_to_draft_is_refused(self):
        self.version.status = TaskVersion.Status.DRAFT
        self.version.published_at = None
        with self.assertRaises(PublishedVersionError):
            self.version.save()

    def test_version_delete_is_refused(self):
        with self.assertRaises(PublishedVersionError):
            self.version.delete()

    def test_queryset_update_and_delete_are_refused(self):
        with self.assertRaises(PublishedVersionError):
            TaskVersion.objects.filter(task=self.task).update(title="X")
        with self.assertRaises(PublishedVersionError):
            TaskVersion.objects.all().delete()
        self.assertEqual(TaskVersion.objects.count(), 1)

    def test_children_save_and_delete_are_refused(self):
        self.requirement.label = "Neu"
        with self.assertRaises(PublishedVersionError):
            self.requirement.save()
        self.hint.text = "Neu"
        with self.assertRaises(PublishedVersionError):
            self.hint.save()
        with self.assertRaises(PublishedVersionError):
            self.requirement.delete()
        with self.assertRaises(PublishedVersionError):
            self.hint.delete()

    def test_children_cannot_be_added(self):
        with self.assertRaises(PublishedVersionError):
            Hint.objects.create(task_version=self.version, key="neu", text="x")
        with self.assertRaises(PublishedVersionError):
            TaskRequirement.objects.bulk_create(
                [
                    TaskRequirement(
                        task_version=self.version, key="neu", type="file", label="x"
                    )
                ]
            )

    def test_children_cannot_be_moved_out_of_a_published_version(self):
        draft = make_version(self.task, with_children=False)
        self.requirement.task_version = draft
        with self.assertRaises(PublishedVersionError):
            self.requirement.save()

    def test_children_bulk_update_and_delete_are_refused(self):
        with self.assertRaises(PublishedVersionError):
            TaskRequirement.objects.filter(task_version=self.version).update(label="X")
        with self.assertRaises(PublishedVersionError):
            Hint.objects.all().delete()
        self.assertEqual(self.version.requirements.count(), 2)

    def test_task_with_published_version_cannot_be_deleted(self):
        with self.assertRaises(models.ProtectedError):
            self.task.delete()
        self.assertTrue(TaskVersion.objects.filter(pk=self.version.pk).exists())

    def test_drafts_stay_editable(self):
        draft = make_version(self.task)
        draft.title = "Neu"
        draft.save()
        draft.requirements.update(label="Geändert")
        draft.hints.all().delete()
        draft.delete()
        self.assertFalse(TaskVersion.objects.filter(pk=draft.pk).exists())

    def test_task_with_only_drafts_can_be_deleted(self):
        task = make_task("entwurf")
        draft = make_version(task)
        task.delete()
        self.assertFalse(TaskVersion.objects.filter(pk=draft.pk).exists())
        self.assertFalse(TaskRequirement.objects.filter(task_version=draft.pk).exists())

    def test_stable_task_fields_stay_editable(self):
        self.task.order = 5
        self.task.is_archived = True
        self.task.save()


class ValidationTests(TestCase):
    def setUp(self):
        self.task = make_task()
        self.version = make_version(self.task, with_children=False)

    def requirement(self, **fields):
        data = {"task_version": self.version, "key": "a", "type": "text", "label": "A"}
        return TaskRequirement(**{**data, **fields})

    def test_keys_unique_per_version(self):
        Hint.objects.create(task_version=self.version, key="k", text="x")
        with self.assertRaises(ValidationError):
            Hint(task_version=self.version, key="k", text="y").full_clean()

    def test_same_key_allowed_in_another_version(self):
        self.version.requirements.create(key="a", type="text", label="A")
        self.version.publish()
        draft = make_version(self.task, with_children=False)
        self.requirement(task_version=draft).full_clean()

    def test_counts(self):
        with self.assertRaisesMessage(ValidationError, "nicht grösser"):
            self.requirement(min_count=3, max_count=2).full_clean()
        with self.assertRaisesMessage(ValidationError, "mindestens 1"):
            self.requirement(min_count=0).full_clean()
        self.requirement(required=False, min_count=0).full_clean()

    def test_unknown_type_and_bad_options(self):
        with self.assertRaises(ValidationError):
            self.requirement(type="video").full_clean()
        with self.assertRaises(ValidationError):
            self.requirement(options=["pdf"]).full_clean()

    def test_task_published_only_with_published_version(self):
        self.task.is_published = True
        with self.assertRaisesMessage(ValidationError, "veröffentlichte Version"):
            self.task.full_clean()
        self.version.requirements.create(key="a", type="text", label="A")
        self.version.publish()
        self.task.full_clean()

    def test_topic_and_badge_are_protected(self):
        badge = Badge.objects.create(name="Linie")
        self.task.badge = badge
        self.task.save()
        with self.assertRaises(models.ProtectedError):
            badge.delete()
        with self.assertRaises(models.ProtectedError):
            self.task.topic.delete()
