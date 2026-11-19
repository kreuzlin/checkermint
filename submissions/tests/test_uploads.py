"""Photo and file requirements (brief 5.6, 5.7, ADR 0009, #24)."""

import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.roles import COACH_GROUP_NAME
from core.private_files import private_file_url
from submissions.models import Submission, SubmissionItem
from tasks.models import Task, TaskRequirement, TaskVersion, Topic

from .test_form import review

User = get_user_model()

IN_MEMORY = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def jpeg(name="roboter.jpg", size=(800, 600), orientation=None, gps=False):
    image = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if gps:
        exif[0x8825] = {1: "N", 2: (47.0, 25.0, 0.0)}
        exif[0x010F] = "Kamera AG"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def heic(name="iphone.heic"):
    import pillow_heif

    buffer = io.BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", (300, 200), (10, 120, 10))).save(
        buffer, quality=80
    )
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/heic")


def upload_task(slug="bruecke", photos=(2, 3), file_options=None):
    """Published task: 2–3 required photos and an optional CAD file."""
    topic, _ = Topic.objects.get_or_create(name="Konstruktion", slug="konstruktion")
    task = Task.objects.create(topic=topic, slug=slug)
    version = TaskVersion.objects.create(
        task=task, title="Brücke", instructions="Baue eine Brücke."
    )
    TaskRequirement.objects.create(
        task_version=version,
        key="fotos",
        type="photo",
        label="Fotos",
        min_count=photos[0],
        max_count=photos[1],
    )
    TaskRequirement.objects.create(
        task_version=version,
        key="cad",
        type="file",
        label="CAD-Datei",
        required=False,
        min_count=0,
        max_count=1,
        options=file_options or {},
        order=1,
    )
    version.publish()
    task.is_published = True
    task.save()
    return task, version


def open_image(field):
    with field.open("rb") as stored:
        return Image.open(io.BytesIO(stored.read()))


@override_settings(STORAGES=IN_MEMORY)
class PhotoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.version = upload_task()
        self.url = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.detail = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)

    def post(self, action="speichern", **data):
        return self.client.post(self.url, {"aktion": action, **data})

    def photos(self):
        return list(
            SubmissionItem.objects.filter(
                submission__status="draft", requirement__key="fotos"
            ).order_by("order")
        )

    def test_photo_is_reencoded_without_metadata_with_thumbnail(self):
        response = self.post(fotos=[jpeg(gps=True, size=(3000, 1500))])
        self.assertRedirects(response, self.url)
        item = self.photos()[0]
        self.assertEqual(item.original_filename, "roboter.jpg")
        self.assertRegex(item.file.name, r"^einreichungen/[0-9a-f]{32}\.jpg$")
        stored = open_image(item.file)
        self.assertEqual(stored.format, "JPEG")
        self.assertEqual(stored.size, (2000, 1000))
        self.assertEqual(dict(stored.getexif()), {})
        self.assertEqual(item.data, {"width": 2000, "height": 1000})
        self.assertLessEqual(max(open_image(item.thumbnail).size), 400)

    def test_photo_is_auto_rotated(self):
        self.post(fotos=[jpeg(size=(800, 600), orientation=6)])
        self.assertEqual(open_image(self.photos()[0].file).size, (600, 800))

    def test_heic_becomes_jpeg(self):
        self.post(fotos=[heic()])
        item = self.photos()[0]
        self.assertEqual(open_image(item.file).format, "JPEG")
        self.assertEqual(item.original_filename, "iphone.heic")

    def test_non_images_are_rejected_with_the_file_name(self):
        fake = SimpleUploadedFile("virus.jpg", b"MZ not an image")
        response = self.post(fotos=[fake])
        self.assertContains(response, "virus.jpg: Diese Datei ist kein lesbares Bild.")
        self.assertFalse(SubmissionItem.objects.exists())

    @override_settings(UPLOAD_MAX_PHOTO_MB=1)
    def test_size_limit_from_settings(self):
        big = SimpleUploadedFile("gross.jpg", b"x" * (1024 * 1024 + 1))
        response = self.post(fotos=[big])
        self.assertContains(response, "zu gross (höchstens 1 MB)")
        self.assertContains(self.client.get(self.url), "je höchstens 1 MB")

    def test_photos_stay_in_the_draft_and_can_be_removed(self):
        self.post(fotos=[jpeg("a.jpg"), jpeg("b.jpg")])
        self.post(fotos=[jpeg("c.jpg")])
        self.assertEqual(
            [i.original_filename for i in self.photos()], ["a.jpg", "b.jpg", "c.jpg"]
        )
        page = self.client.get(self.url)
        self.assertContains(page, 'name="fotos-entfernen"')
        self.assertContains(page, "gespeichert: 3")

        first = self.photos()[0]
        storage, name = first.file.storage, first.file.name
        with self.captureOnCommitCallbacks(execute=True):
            self.post(**{"fotos-entfernen": [str(first.pk)]})
        self.assertEqual(
            [i.original_filename for i in self.photos()], ["b.jpg", "c.jpg"]
        )
        self.assertEqual([i.order for i in self.photos()], [0, 1])
        self.assertFalse(storage.exists(name))

    def test_at_most_max_count(self):
        self.post(fotos=[jpeg("a.jpg"), jpeg("b.jpg")])
        response = self.post(fotos=[jpeg("c.jpg"), jpeg("d.jpg")])
        self.assertContains(response, "Höchstens 3.")
        self.assertEqual(len(self.photos()), 2)

    def test_submit_needs_min_count(self):
        response = self.post("einreichen", fotos=[jpeg()])
        self.assertContains(response, "Das fehlt noch.")
        response = self.post("einreichen", fotos=[jpeg("b.jpg")])
        self.assertRedirects(response, self.detail)
        self.assertEqual(Submission.objects.get().status, Submission.Status.SUBMITTED)
        page = self.client.get(self.detail)
        self.assertContains(page, 'class="photo-thumb"')
        self.assertContains(page, 'alt="Foto: Fotos (1)"')

    def test_resubmission_copies_the_photos(self):
        self.post("einreichen", fotos=[jpeg("a.jpg"), jpeg("b.jpg")])
        first = Submission.objects.get()
        review(first, Submission.Status.NEEDS_REVISION, feedback="Schärfer bitte.")
        old_names = set(first.items.values_list("file", flat=True))

        self.assertContains(self.client.get(self.url), "a.jpg")
        keep = first.items.get(original_filename="b.jpg")
        # Remove a.jpg, keep b.jpg, add c.jpg.
        removed = first.items.get(original_filename="a.jpg")
        self.post(
            "einreichen",
            fotos=[jpeg("c.jpg")],
            **{"fotos-entfernen": [str(removed.pk)]},
        )
        second = Submission.objects.exclude(pk=first.pk).get()
        self.assertEqual(second.status, Submission.Status.SUBMITTED)
        names = [i.original_filename for i in second.items.order_by("order")]
        self.assertEqual(names, ["b.jpg", "c.jpg"])
        # Copies with their own files; the reviewed submission is untouched.
        copied = second.items.get(original_filename="b.jpg")
        self.assertNotIn(copied.file.name, old_names)
        self.assertTrue(copied.file.storage.exists(keep.file.name))
        self.assertEqual(first.items.count(), 2)

    def test_foreign_items_cannot_be_kept(self):
        other = User.objects.create_user("ben", password="geheim123")
        self.client.force_login(other)
        self.client.post(self.url, {"aktion": "speichern", "fotos": [jpeg("ben.jpg")]})
        ben_item = SubmissionItem.objects.get()
        self.client.force_login(self.user)
        # Without own photos there is no remove field: the id is ignored.
        self.post(**{"fotos-entfernen": [str(ben_item.pk)]})
        self.assertEqual(self.photos(), [ben_item])
        # With own photos, a foreign id is not a valid choice.
        self.post(fotos=[jpeg("anna.jpg")])
        response = self.post(**{"fotos-entfernen": [str(ben_item.pk)]})
        self.assertContains(response, "keine gültige Auswahl")
        ben_item.refresh_from_db()
        self.assertEqual(ben_item.submission.user, other)


@override_settings(STORAGES=IN_MEMORY)
class FileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, _ = upload_task(file_options={"extensions": [".stl", ".step"]})
        self.url = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)

    def post(self, **data):
        return self.client.post(self.url, {"aktion": "speichern", **data})

    def test_file_is_stored_as_uploaded(self):
        self.post(cad=SimpleUploadedFile("Brücke von Anna.STL", b"solid bruecke"))
        item = SubmissionItem.objects.get()
        self.assertEqual(item.original_filename, "Brücke von Anna.STL")
        self.assertRegex(item.file.name, r"^einreichungen/[0-9a-f]{32}\.stl$")
        with item.file.open("rb") as stored:
            self.assertEqual(stored.read(), b"solid bruecke")
        self.assertFalse(item.thumbnail)

    def test_extensions_and_size(self):
        response = self.post(cad=SimpleUploadedFile("a.exe", b"MZ"))
        self.assertContains(response, "a.exe: Diese Dateiendung ist hier nicht erlaubt")
        with self.settings(UPLOAD_MAX_FILE_MB=1):
            response = self.post(
                cad=SimpleUploadedFile("a.stl", b"x" * (1024 * 1024 + 1))
            )
        self.assertContains(response, "zu gross (höchstens 1 MB)")
        response = self.post(cad=SimpleUploadedFile("leer.stl", b""))
        self.assertContains(response, "leer")
        self.assertFalse(SubmissionItem.objects.exists())

    def test_only_one_file_when_max_count_is_1(self):
        self.post(cad=SimpleUploadedFile("a.stl", b"solid a"))
        response = self.post(cad=SimpleUploadedFile("b.stl", b"solid b"))
        self.assertContains(response, "Höchstens 1.")


@override_settings(STORAGES=IN_MEMORY)
class AccessTests(TestCase):
    """Files of submissions: the participant and coaches only (ADR 0009)."""

    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        self.task, _ = upload_task()
        url = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.client.force_login(self.anna)
        self.client.post(
            url,
            {
                "aktion": "speichern",
                "fotos": [jpeg()],
                "cad": SimpleUploadedFile(
                    "<script>.html", b"<script>alert(1)</script>"
                ),
            },
        )
        self.photo = SubmissionItem.objects.get(requirement__key="fotos")
        self.file = SubmissionItem.objects.get(requirement__key="cad")
        self.photo_url = private_file_url("einreichungsfoto", self.photo)
        self.thumb_url = private_file_url("einreichungsfoto", self.photo, "vorschau")
        self.file_url = private_file_url("einreichungsdatei", self.file)

    def test_owner_sees_photo_inline_and_file_as_download(self):
        response = self.client.get(self.photo_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.get(self.thumb_url).status_code, 200)

        response = self.client.get(self.file_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_coach_has_access(self):
        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(coach)
        for url in (self.photo_url, self.thumb_url, self.file_url):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_other_participants_and_anonymous_get_404(self):
        ben = User.objects.create_user("ben", password="geheim123")
        for login in (ben, None):
            if login:
                self.client.force_login(login)
            else:
                self.client.logout()
            for url in (self.photo_url, self.thumb_url, self.file_url):
                self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_kinds_do_not_mix(self):
        wrong = [
            private_file_url("einreichungsfoto", self.file),
            private_file_url("einreichungsdatei", self.photo),
            private_file_url("einreichungsdatei", self.file, "vorschau"),
        ]
        for url in wrong:
            self.assertEqual(self.client.get(url).status_code, 404, url)
