"""Who added a photo or file to a submission (#77)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from submissions.models import Submission, SubmissionItem
from submissions.switching import switch_version
from submissions.upload_links import make_token

from .test_form import review
from .test_switching import publish_v2
from .test_uploads import IN_MEMORY, jpeg, upload_task

User = get_user_model()


@override_settings(STORAGES=IN_MEMORY)
class UploadAuthorTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla")
        self.task, self.v1 = upload_task(photos=(1, 5))
        self.edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.coach_url = reverse(
            "submissions:coach_upload",
            kwargs={"nickname": "RoboAnna", "slug": self.task.slug},
        )

    def upload_all_three_ways(self):
        self.client.force_login(self.anna)
        self.client.post(self.edit, {"aktion": "speichern", "fotos": [jpeg("own.jpg")]})
        draft = Submission.objects.get()
        self.client.logout()
        phone = reverse("submissions:phone_upload", kwargs={"token": make_token(draft)})
        self.client.post(phone, {"fotos": [jpeg("phone.jpg")]})
        self.client.force_login(self.coach)
        self.client.post(self.coach_url, {"fotos": [jpeg("coach.jpg")]})
        return draft

    def origins(self, submission):
        return {
            item.original_filename: (item.uploaded_by, item.via_phone)
            for item in submission.items.all()
        }

    def test_recorded_for_form_phone_and_coach(self):
        draft = self.upload_all_three_ways()
        self.assertEqual(
            self.origins(draft),
            {
                "own.jpg": (self.anna, False),
                "phone.jpg": (None, True),
                "coach.jpg": (self.coach, False),
            },
        )

    def test_shown_in_form_task_page_and_review(self):
        draft = self.upload_all_three_ways()
        self.client.force_login(self.anna)
        response = self.client.get(self.edit)
        self.assertContains(response, "hochgeladen von Coach CoachCarla", count=1)
        self.assertContains(response, "per Handy hochgeladen", count=1)
        self.client.post(self.edit, {"aktion": "einreichen"})
        detail = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.assertContains(self.client.get(detail), "hochgeladen von Coach CoachCarla")
        self.client.force_login(self.coach)
        review_url = reverse("submissions:review", kwargs={"pk": draft.pk})
        self.assertContains(
            self.client.get(review_url), "hochgeladen von Coach CoachCarla"
        )

    def test_never_on_the_public_profile(self):
        self.upload_all_three_ways()
        self.client.logout()
        public = reverse("accounts:public_profile", kwargs={"nickname": "RoboAnna"})
        response = self.client.get(public)
        self.assertNotContains(response, "hochgeladen")

    def test_resubmission_keeps_the_uploader(self):
        draft = self.upload_all_three_ways()
        self.client.force_login(self.anna)
        self.client.post(self.edit, {"aktion": "einreichen"})
        draft.refresh_from_db()
        review(draft, Submission.Status.NEEDS_REVISION, feedback="Mehr")
        self.client.post(self.edit, {"aktion": "speichern"})  # copies the photos
        new_draft = Submission.objects.get(status=Submission.Status.DRAFT)
        self.assertNotEqual(new_draft.pk, draft.pk)
        self.assertEqual(self.origins(new_draft), self.origins(draft))

    def test_version_switch_keeps_the_uploader(self):
        draft = self.upload_all_three_ways()
        before = self.origins(draft)
        v2 = publish_v2(self.task)
        switch_version(self.anna, self.task, v2.pk)
        new_draft = Submission.objects.get(status=Submission.Status.DRAFT)
        self.assertEqual(new_draft.task_version, v2)
        self.assertEqual(self.origins(new_draft), before)

    def test_deleted_coach_account_leaves_the_item(self):
        draft = self.upload_all_three_ways()
        self.coach.delete()
        item = SubmissionItem.objects.get(
            submission=draft, original_filename="coach.jpg"
        )
        self.assertIsNone(item.uploaded_by)
