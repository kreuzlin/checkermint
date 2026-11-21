"""QR code upload links and the phone upload page (brief 5.7, #28)."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from submissions.models import Submission, SubmissionItem
from submissions.upload_links import (
    SALT,
    InvalidUploadLink,
    make_token,
    target_for_token,
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
        return reverse(
            "submissions:phone_upload",
            kwargs={"token": make_token(draft.user, draft.task)},
        )

    def test_qr_code_right_away_and_the_phone_creates_the_draft(self):
        """#130: after "Aufgabe starten" there is no draft yet; the QR code
        must be there anyway, and the first phone upload creates the draft."""
        response = self.client.get(self.edit)
        self.assertNotContains(response, "Speichere zuerst einen Entwurf")
        self.assertContains(response, "QR-Code zum Hochladen mit dem Handy")
        self.assertFalse(Submission.objects.exists())

        url = response.context["phone_upload"]["url"].replace("http://testserver", "")
        self.client.logout()
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertFalse(Submission.objects.exists())  # GET creates nothing

        self.client.post(url, {"fotos": [jpeg("handy.jpg")]})
        draft = Submission.objects.get()
        self.assertEqual(draft.status, Submission.Status.DRAFT)
        self.assertEqual(draft.task_version, self.version)
        self.assertEqual(
            list(draft.items.values_list("original_filename", "via_phone")),
            [("handy.jpg", True)],
        )

        # Saving on the laptop afterwards keeps the phone photo.
        self.client.force_login(self.user)
        self.client.post(self.edit, {"aktion": "speichern"})
        self.assertEqual(draft.items.count(), 1)

    def test_form_shows_qr_code_with_a_signed_link(self):
        draft = self.save_draft()
        response = self.client.get(self.edit)
        self.assertContains(response, "<svg")
        self.assertContains(response, "QR-Code zum Hochladen mit dem Handy")
        url = response.context["phone_upload"]["url"]
        self.assertTrue(url.startswith("http://testserver/hochladen/"))
        token = url.rstrip("/").rsplit("/", 1)[1]
        self.assertEqual(target_for_token(token), (draft.user, draft.task))

    def test_no_qr_code_for_tasks_without_uploads(self):
        task, _ = text_and_code_task()
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        self.client.post(url, {"aktion": "speichern", "erklaerung": "x"})
        self.assertNotContains(self.client.get(url), "Fotos mit dem Handy")

    def test_phone_page_offers_photos_only(self):
        """#134: the phone uploads photos; files (code, 3D models) come from
        the laptop or a coach (brief 5.7)."""
        draft = self.save_draft()
        url = self.phone_url(draft)
        self.client.logout()
        page = self.client.get(url)
        self.assertContains(page, 'name="fotos"')
        self.assertNotContains(page, 'name="cad"')
        self.assertNotContains(page, "CAD-Datei")
        # A file sent anyway for the file requirement is ignored.
        cad = SimpleUploadedFile("modell.stl", b"solid x")
        response = self.client.post(url, {"cad": [cad]})
        self.assertContains(response, "Wähle zuerst ein Foto aus.")
        self.assertFalse(SubmissionItem.objects.exists())

    def test_no_qr_code_for_tasks_with_files_but_no_photos(self):
        from tasks.models import Task, TaskRequirement, TaskVersion, Topic

        topic, _ = Topic.objects.get_or_create(name="Code", slug="code")
        task = Task.objects.create(topic=topic, slug="nur-datei", is_published=False)
        version = TaskVersion.objects.create(
            task=task, title="Nur Datei", instructions="Lade dein Programm hoch."
        )
        TaskRequirement.objects.create(
            task_version=version, key="cad", type="file", label="CAD-Datei"
        )
        version.publish()
        task.is_published = True
        task.save()
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        response = self.client.get(url)
        self.assertContains(response, "CAD-Datei")  # the laptop form keeps it
        self.assertNotContains(response, "Fotos mit dem Handy")

    def test_upload_passes_the_real_csrf_check_with_an_origin(self):
        """#128: browsers send the page's origin; the CSRF check must pass.

        The default test client neither enforces CSRF nor sends an Origin
        header, which is how "Origin: null" (from no-referrer) slipped
        through.
        """
        draft = self.save_draft()
        url = self.phone_url(draft)
        phone = Client(enforce_csrf_checks=True)
        page = phone.get(url)
        token = page.context["csrf_token"]
        response = phone.post(
            url,
            {"csrfmiddlewaretoken": str(token), "fotos": [jpeg("handy.jpg")]},
            HTTP_ORIGIN="http://testserver",
        )
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.assertEqual(draft.items.count(), 1)

        # What no-referrer made the iPhone send: rejected, nothing stored.
        response = phone.post(
            url,
            {"csrfmiddlewaretoken": str(token), "fotos": [jpeg("handy2.jpg")]},
            HTTP_ORIGIN="null",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(draft.items.count(), 1)

    def test_phone_uploads_without_login_into_the_draft(self):
        draft = self.save_draft()
        url = self.phone_url(draft)
        self.client.logout()
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "«Brücke»")
        # Only the origin as referrer, never the token (#128).
        self.assertContains(page, '<meta name="referrer" content="strict-origin">')
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
        self.assertContains(response, "Wähle zuerst ein Foto aus.")
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
        token = make_token(draft.user, draft.task)
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
        self.assertContains(response, "wartet auf einen Coach", status_code=410)
        self.assertEqual(draft.items.count(), 1)
        self.assertEqual(Submission.objects.count(), 1)

    def test_link_is_bound_to_the_participant(self):
        draft = self.save_draft()
        other = User.objects.create_user("ben", password="geheim123")
        from django.core import signing

        # Old link format (draft id) with someone else's user id.
        forged = signing.dumps({"s": draft.pk, "u": other.pk}, salt=SALT)
        with self.assertRaises(InvalidUploadLink):
            target_for_token(forged)
        # A link names one participant: Ben's link never reaches Anna's draft.
        bens = make_token(other, draft.task)
        url = reverse("submissions:phone_upload", kwargs={"token": bens})
        self.client.logout()
        self.client.post(url, {"fotos": [jpeg("ben.jpg")]})
        self.assertEqual(draft.items.count(), 0)
        self.assertEqual(Submission.objects.filter(user=other).count(), 1)

    def test_old_links_with_a_draft_id_still_work(self):
        from django.core import signing

        draft = self.save_draft()
        old = signing.dumps(
            {"s": draft.pk, "u": self.user.pk}, salt=SALT, compress=True
        )
        self.assertEqual(target_for_token(old), (self.user, draft.task))

    def test_no_link_for_coaches_or_locked_tasks(self):
        from django.contrib.auth.models import Group
        from django.core import signing

        from accounts.roles import COACH_GROUP_NAME

        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        token = signing.dumps({"t": self.task.pk, "u": coach.pk}, salt=SALT)
        with self.assertRaises(InvalidUploadLink):
            target_for_token(token)
        self.task.min_level = 5
        self.task.save(update_fields=["min_level"])
        with self.assertRaisesMessage(InvalidUploadLink, "gesperrt"):
            target_for_token(make_token(self.user, self.task))
