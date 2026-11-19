"""Photos from the phone appear in the draft on the other device (#29)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from submissions.models import Submission
from submissions.upload_links import make_token

from .test_uploads import IN_MEMORY, jpeg, upload_task

User = get_user_model()


@override_settings(STORAGES=IN_MEMORY)
class LiveUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, _ = upload_task(photos=(1, 3))
        self.edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.stored = reverse(
            "submissions:stored", kwargs={"slug": self.task.slug, "key": "fotos"}
        )
        self.client.force_login(self.user)

    def save_draft(self):
        self.client.post(self.edit, {"aktion": "speichern"})
        return Submission.objects.get()

    def phone_upload(self, draft, *names):
        url = reverse("submissions:phone_upload", kwargs={"token": make_token(draft)})
        self.client.post(url, {"fotos": [jpeg(name) for name in names]})

    def test_form_polls_only_with_a_draft(self):
        response = self.client.get(self.edit)
        self.assertNotContains(response, "htmx-2.0.4.min.js")
        self.assertNotContains(response, "hx-get")
        self.save_draft()
        response = self.client.get(self.edit)
        self.assertContains(response, "/static/core/js/htmx-2.0.4.min.js")
        self.assertContains(response, f'hx-get="{self.stored}?stand=0"')
        self.assertContains(response, 'hx-trigger="every 5s"')
        self.assertContains(response, "erscheinen hier automatisch")

    def test_unchanged_answers_204_changed_returns_the_list(self):
        draft = self.save_draft()
        self.assertEqual(self.client.get(self.stored, {"stand": "0"}).status_code, 204)

        self.phone_upload(draft, "handy.jpg")
        item = draft.items.get()
        response = self.client.get(self.stored, {"stand": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "handy.jpg")
        self.assertContains(response, f'value="{item.pk}"')
        self.assertContains(response, f"?stand={item.pk}")
        self.assertContains(response, "Gespeichert: 1.")
        self.assertEqual(
            self.client.get(self.stored, {"stand": str(item.pk)}).status_code, 204
        )

    def test_ticked_checkboxes_survive_a_refresh(self):
        draft = self.save_draft()
        self.phone_upload(draft, "a.jpg")
        first = draft.items.get()
        self.phone_upload(draft, "b.jpg")
        response = self.client.get(
            self.stored, {"stand": str(first.pk), "fotos-entfernen": [str(first.pk)]}
        )
        self.assertContains(response, f'value="{first.pk}" checked')

    def test_polling_stops_when_nothing_to_show(self):
        draft = self.save_draft()
        self.client.post(self.edit, {"aktion": "speichern", "fotos": [jpeg()]})
        self.client.post(self.edit, {"aktion": "einreichen"})
        draft.refresh_from_db()
        self.assertEqual(draft.status, Submission.Status.SUBMITTED)
        self.assertEqual(self.client.get(self.stored).status_code, 286)

        other = reverse(
            "submissions:stored", kwargs={"slug": self.task.slug, "key": "gibts-nicht"}
        )
        self.assertEqual(self.client.get(other).status_code, 286)

    def test_only_own_draft(self):
        draft = self.save_draft()
        self.phone_upload(draft, "anna.jpg")
        ben = User.objects.create_user("ben", password="geheim123")
        self.client.force_login(ben)
        self.assertEqual(self.client.get(self.stored).status_code, 286)
        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(coach)
        self.assertEqual(self.client.get(self.stored).status_code, 286)
        self.client.logout()
        self.assertEqual(self.client.get(self.stored).status_code, 302)

    def test_file_requirements_are_polled_too(self):
        self.save_draft()
        url = reverse(
            "submissions:stored", kwargs={"slug": self.task.slug, "key": "cad"}
        )
        self.assertEqual(self.client.get(url, {"stand": "0"}).status_code, 204)
