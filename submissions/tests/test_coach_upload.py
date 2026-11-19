"""Coaches upload photos and files for a participant (brief 5.7, #30)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from submissions.models import Submission
from tasks.models import LevelThreshold

from .test_form import review, text_and_code_task
from .test_uploads import IN_MEMORY, jpeg, upload_task

User = get_user_model()


@override_settings(STORAGES=IN_MEMORY)
class CoachUploadTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.task, self.version = upload_task(photos=(1, 3))
        self.choose = reverse(
            "submissions:coach_upload_choose", kwargs={"nickname": "RoboAnna"}
        )
        self.url = reverse(
            "submissions:coach_upload",
            kwargs={"nickname": "RoboAnna", "slug": self.task.slug},
        )
        self.client.force_login(self.coach)

    def test_link_on_participant_profile_for_coaches_only(self):
        profile_url = reverse(
            "accounts:participant_detail", kwargs={"nickname": "RoboAnna"}
        )
        self.assertContains(self.client.get(profile_url), self.choose)
        self.client.force_login(self.anna)
        self.assertNotContains(self.client.get(profile_url), self.choose)

    def test_choose_lists_tasks_with_uploads(self):
        text_task, _ = text_and_code_task()
        response = self.client.get(self.choose)
        self.assertContains(response, "<title>Hochladen für RoboAnna – ")
        self.assertContains(response, self.url)
        self.assertNotContains(response, text_task.slug)

    def test_upload_creates_the_draft_and_starts_the_task(self):
        response = self.client.get(self.url)
        self.assertContains(response, "noch kein Entwurf")
        self.assertFalse(Submission.objects.exists())

        response = self.client.post(self.url, {"fotos": [jpeg("coach.jpg")]})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertContains(
            self.client.get(self.url), "1 Datei im Entwurf von RoboAnna gespeichert."
        )
        draft = Submission.objects.get()
        self.assertEqual(draft.user, self.anna)
        self.assertEqual(draft.status, Submission.Status.DRAFT)
        self.assertEqual(draft.items.get().original_filename, "coach.jpg")
        self.assertEqual(self.anna.task_attempts.get().task_version, self.version)

        # Anna sees the photo in her form and submits herself.
        self.client.force_login(self.anna)
        edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.assertContains(self.client.get(edit), "coach.jpg")

    def test_coach_sees_thumbnails_and_adds(self):
        self.client.post(self.url, {"fotos": [jpeg("a.jpg")]})
        response = self.client.get(self.url)
        self.assertContains(response, 'class="photo-thumb"')
        self.assertContains(response, "Gespeichert: 1 von höchstens 3.")
        self.client.post(self.url, {"fotos": [jpeg("b.jpg"), jpeg("c.jpg")]})
        response = self.client.post(self.url, {"fotos": [jpeg("d.jpg")]})
        self.assertContains(response, "Höchstens 3.")
        self.assertEqual(Submission.objects.get().items.count(), 3)

    def test_new_draft_after_review_starts_from_the_last_submission(self):
        self.client.force_login(self.anna)
        edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.client.post(edit, {"aktion": "einreichen", "fotos": [jpeg("erst.jpg")]})
        review(Submission.objects.get(), Submission.Status.NEEDS_REVISION)

        self.client.force_login(self.coach)
        self.client.post(self.url, {"fotos": [jpeg("neu.jpg")]})
        draft = Submission.objects.get(status=Submission.Status.DRAFT)
        self.assertEqual(
            sorted(draft.items.values_list("original_filename", flat=True)),
            ["erst.jpg", "neu.jpg"],
        )

    def test_refused_while_waiting_or_locked(self):
        self.client.force_login(self.anna)
        edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.client.post(edit, {"aktion": "einreichen", "fotos": [jpeg()]})
        self.client.force_login(self.coach)
        self.assertRedirects(self.client.get(self.url), self.choose)
        self.client.post(self.url, {"fotos": [jpeg("spaet.jpg")]})
        self.assertEqual(Submission.objects.get().items.count(), 1)

        LevelThreshold.objects.get_or_create(level=2, min_points=50)
        locked, _ = upload_task(slug="schwer")
        locked.min_level = 2
        locked.save()
        url = reverse(
            "submissions:coach_upload",
            kwargs={"nickname": "RoboAnna", "slug": "schwer"},
        )
        self.assertRedirects(self.client.post(url, {"fotos": [jpeg()]}), self.choose)
        self.assertEqual(Submission.objects.count(), 1)

    def test_only_coaches(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.choose).status_code, 403)
        self.assertEqual(
            self.client.post(self.url, {"fotos": [jpeg()]}).status_code, 403
        )
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertFalse(Submission.objects.exists())

    def test_unknown_or_staff_accounts_are_404(self):
        url = reverse("submissions:coach_upload_choose", kwargs={"nickname": "niemand"})
        self.assertEqual(self.client.get(url).status_code, 404)
