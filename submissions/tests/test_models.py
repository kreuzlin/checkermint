"""Submission models (brief 5.6, ADR 0010, ADR 0011, #22)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import IntegrityError, models, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.roles import COACH_GROUP_NAME
from submissions.models import Submission, SubmissionItem, SubmissionLockedError
from tasks.tests.test_attempts import new_version, published_task
from tasks.tests.test_versions import make_task, make_version

User = get_user_model()


def make_submission(user, version, **fields):
    return Submission.objects.create(
        user=user, task=version.task, task_version=version, **fields
    )


def submit(submission):
    submission.status = Submission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save()


class SubmissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = published_task()

    def test_new_submission_is_a_draft(self):
        submission = make_submission(self.user, self.v1)
        self.assertEqual(submission.status, Submission.Status.DRAFT)
        self.assertIsNone(submission.submitted_at)

    def test_only_published_versions_of_the_same_task(self):
        draft = self.task.create_draft()
        with self.assertRaises(ValueError):
            make_submission(self.user, draft)
        _, other_version = published_task("andere")
        with self.assertRaises(ValueError):
            Submission.objects.create(
                user=self.user, task=self.task, task_version=other_version
            )

    def test_version_never_changes(self):
        submission = make_submission(self.user, self.v1)
        submission.task_version = new_version(self.task)
        with self.assertRaises(ValueError):
            submission.save()

    def test_one_draft_per_participant_and_task(self):
        first = make_submission(self.user, self.v1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_submission(self.user, self.v1)
        submit(first)
        # After submitting, a new draft (resubmission) is allowed.
        make_submission(self.user, self.v1)
        self.assertEqual(Submission.objects.count(), 2)

    def test_stars_only_on_approved_submissions(self):
        submission = make_submission(self.user, self.v1)
        submit(submission)
        submission.stars = 2
        with self.assertRaises(IntegrityError), transaction.atomic():
            submission.save()

        submission.status = Submission.Status.NEEDS_REVISION
        submission.reviewed_at = timezone.now()
        with self.assertRaises(IntegrityError), transaction.atomic():
            submission.save()

        submission.status = Submission.Status.APPROVED
        submission.save()
        submission.stars = None
        with self.assertRaises(IntegrityError), transaction.atomic():
            submission.save()

    def test_stars_between_1_and_3(self):
        submission = make_submission(self.user, self.v1)
        submission.status = Submission.Status.APPROVED
        submission.submitted_at = submission.reviewed_at = timezone.now()
        for stars in (0, 4):
            submission.stars = stars
            with self.assertRaises(IntegrityError), transaction.atomic():
                submission.save()

    def test_timestamps_match_the_status(self):
        submission = make_submission(self.user, self.v1)
        submission.status = Submission.Status.SUBMITTED
        with self.assertRaises(IntegrityError), transaction.atomic():
            submission.save()  # no submitted_at
        submission.submitted_at = timezone.now()
        submission.status = Submission.Status.NEEDS_REVISION
        with self.assertRaises(IntegrityError), transaction.atomic():
            submission.save()  # no reviewed_at

    def test_tasks_and_versions_with_submissions_cannot_be_deleted(self):
        make_submission(self.user, self.v1)
        with self.assertRaises(models.ProtectedError):
            self.task.delete()

    def test_deleting_the_user_deletes_their_submissions(self):
        make_submission(self.user, self.v1)
        self.user.delete()
        self.assertFalse(Submission.objects.exists())


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class SubmissionItemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = published_task()
        self.text_req = self.v1.requirements.get(key="erklaerung")
        self.photo_req = self.v1.requirements.get(key="fotos")
        self.submission = make_submission(self.user, self.v1)

    def add_item(self, **fields):
        fields.setdefault("requirement", self.text_req)
        return SubmissionItem.objects.create(submission=self.submission, **fields)

    def test_items_belong_to_requirements_of_the_same_version(self):
        self.add_item(text="Mein Roboter folgt der Linie.")
        other = make_task("andere")
        other_version = make_version(other)
        with self.assertRaises(ValueError):
            self.add_item(requirement=other_version.requirements.first())

    def test_files_get_random_names(self):
        item = self.add_item(
            requirement=self.photo_req,
            file=ContentFile(b"x", name="Anna Müller Roboter.jpg"),
            original_filename="Anna Müller Roboter.jpg",
        )
        self.assertRegex(item.file.name, r"^einreichungen/[0-9a-f]{32}\.jpg$")

    def test_items_are_locked_once_submitted(self):
        item = self.add_item(text="Entwurf")
        submit(self.submission)
        item.text = "Geändert"
        with self.assertRaises(SubmissionLockedError):
            item.save()
        with self.assertRaises(SubmissionLockedError):
            item.delete()
        with self.assertRaises(SubmissionLockedError):
            self.add_item(text="Neu")
        items = SubmissionItem.objects.all()
        with self.assertRaises(SubmissionLockedError):
            items.update(text="Geändert")
        with self.assertRaises(SubmissionLockedError):
            items.delete()
        with self.assertRaises(SubmissionLockedError):
            SubmissionItem.objects.bulk_create(
                [SubmissionItem(submission=self.submission, requirement=self.text_req)]
            )
        self.assertEqual(SubmissionItem.objects.get().text, "Entwurf")

    def test_deleting_a_draft_item_removes_its_files(self):
        item = self.add_item(
            requirement=self.photo_req,
            file=ContentFile(b"x", name="a.jpg"),
            thumbnail=ContentFile(b"y", name="a.jpg"),
        )
        storage, names = item.file.storage, [item.file.name, item.thumbnail.name]
        item.delete()
        for name in names:
            self.assertFalse(storage.exists(name))

    def test_requirements_with_items_are_protected(self):
        self.add_item(text="Hallo")
        with self.assertRaises(models.ProtectedError):
            # Bypass the published-version guard to test the foreign key.
            models.Model.delete(self.text_req)


class SubmissionAdminTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        user = User.objects.create_user("anna", password="geheim123")
        _, version = published_task()
        self.submission = make_submission(user, version)
        self.client.force_login(self.coach)

    def test_coaches_can_view_but_not_change(self):
        list_url = reverse("admin:submissions_submission_changelist")
        self.assertEqual(self.client.get(list_url).status_code, 200)
        change_url = reverse(
            "admin:submissions_submission_change", args=[self.submission.pk]
        )
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(
            self.client.get(reverse("admin:submissions_submission_add")).status_code,
            403,
        )
        delete_url = reverse(
            "admin:submissions_submission_delete", args=[self.submission.pk]
        )
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
        self.assertTrue(Submission.objects.exists())
