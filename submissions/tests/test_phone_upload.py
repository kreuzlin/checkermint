"""QR code upload links and the phone upload page (brief 5.7, #28)."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from submissions.models import Submission, SubmissionItem
from submissions.upload_links import (
    InvalidUploadLink,
    draft_for_token,
    make_token,
)

from .test_form import text_and_code_task
from .test_uploads import IN_MEMORY, jpeg, upload_task

User = get_user_model()


@override_settings(STORAGES=IN_MEMORY)
class PhoneUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(
            user=self.user, nickname="Robo-Anna", real_name="Anna Muster"
        )
        self.task, self.version = upload_task(photos=(1, 3))
        self.edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)

    def save_draft(self):
        self.client.post(self.edit, {"aktion": "speichern"})
        return Submission.objects.get()

    def phone_url(self, draft):
        return reverse("submissions:phone_upload", kwargs={"token": make_token(draft)})

    def test_form_asks_for_a_draft_first(self):
        response = self.client.get(self.edit)
        self.assertContains(response, "Speichere zuerst einen Entwurf")
        self.assertNotContains(response, "<svg")

    def test_form_shows_qr_code_with_a_signed_link(self):
        draft = self.save_draft()
        response = self.client.get(self.edit)
        self.assertContains(response, "<svg")
        self.assertContains(response, "QR-Code zum Hochladen mit dem Handy")
        url = response.context["phone_upload"]["url"]
        self.assertTrue(url.startswith("http://testserver/hochladen/"))
        token = url.rstrip("/").rsplit("/", 1)[1]
        self.assertEqual(draft_for_token(token), draft)

    def test_no_qr_code_for_tasks_without_uploads(self):
        task, _ = text_and_code_task()
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        self.client.post(url, {"aktion": "speichern", "erklaerung": "x"})
        self.assertNotContains(self.client.get(url), "Fotos mit dem Handy")

    def test_phone_uploads_without_login_into_the_draft(self):
        draft = self.save_draft()
        url = self.phone_url(draft)
        self.client.logout()
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "«Brücke»")
        self.assertContains(page, '<meta name="referrer" content="no-referrer">')
        # No personal data on a page without login.
        self.assertNotContains(page, "Anna")

        response = self.client.post(
            url, {"fotos": [jpeg("handy1.jpg"), jpeg("handy2.jpg")]}
        )
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.assertContains(self.client.get(url), "2 Dateien sind hochgeladen.")
        items = draft.items.order_by("order")
        self.assertEqual(
            [i.original_filename for i in items], ["handy1.jpg", "handy2.jpg"]
        )
        # Same image pipeline: thumbnails and re-encoding.
        self.assertTrue(all(i.thumbnail for i in items))

        # More from the phone are added, never replacing.
        self.client.post(url, {"fotos": [jpeg("handy3.jpg")]})
        self.assertEqual(draft.items.count(), 3)
        response = self.client.post(url, {"fotos": [jpeg("handy4.jpg")]})
        self.assertContains(response, "Höchstens 3.")
        self.assertEqual(draft.items.count(), 3)

    def test_photos_from_the_phone_show_up_in_the_form(self):
        draft = self.save_draft()
        self.client.post(self.phone_url(draft), {"fotos": [jpeg("vom-handy.jpg")]})
        response = self.client.get(self.edit)
        self.assertContains(response, "vom-handy.jpg")
        # Saving the full form keeps them.
        self.client.post(self.edit, {"aktion": "speichern"})
        self.assertEqual(draft.items.count(), 1)

    def test_empty_post_and_invalid_files(self):
        draft = self.save_draft()
        url = self.phone_url(draft)
        response = self.client.post(url, {})
        self.assertContains(response, "Wähle zuerst ein Foto oder eine Datei aus.")
        response = self.client.post(
            url, {"fotos": [SimpleUploadedFile("x.jpg", b"nope")]}
        )
        self.assertContains(response, "x.jpg: Diese Datei ist kein lesbares Bild.")
        self.assertFalse(SubmissionItem.objects.exists())

    def test_link_expires_after_30_minutes(self):
        draft = self.save_draft()
        url = self.phone_url(draft)
        later = timezone.now() + timedelta(minutes=31)
        with mock.patch(
            "django.core.signing.time.time", return_value=later.timestamp()
        ):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "abgelaufen", status_code=410)

    def test_tampered_link_is_invalid(self):
        draft = self.save_draft()
        token = make_token(draft)
        url = reverse("submissions:phone_upload", kwargs={"token": token[:-2] + "xx"})
        response = self.client.post(url, {"fotos": [jpeg()]})
        self.assertEqual(response.status_code, 410)
        self.assertFalse(SubmissionItem.objects.exists())

    def test_link_ends_with_the_draft(self):
        draft = self.save_draft()
        url = self.phone_url(draft)
        self.client.post(url, {"fotos": [jpeg()]})
        self.client.post(self.edit, {"aktion": "einreichen"})
        draft.refresh_from_db()
        self.assertEqual(draft.status, Submission.Status.SUBMITTED)
        response = self.client.post(url, {"fotos": [jpeg("spaet.jpg")]})
        self.assertContains(response, "keinen Entwurf mehr", status_code=410)
        self.assertEqual(draft.items.count(), 1)

    def test_link_is_bound_to_the_participant(self):
        draft = self.save_draft()
        other = User.objects.create_user("ben", password="geheim123")
        with self.assertRaises(InvalidUploadLink):
            from django.core import signing

            from submissions.upload_links import SALT

            forged = signing.dumps({"s": draft.pk, "u": other.pk}, salt=SALT)
            draft_for_token(forged)
