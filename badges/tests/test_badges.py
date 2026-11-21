"""Badges with an uploaded image or a placeholder (brief 5.8, ADR 0018, #120)."""

import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.roles import COACH_GROUP_NAME
from badges.admin import UPLOAD_NOTICE
from badges.images import process_badge_image
from badges.models import Badge

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def png(colour=(0, 220, 173, 255), fmt="PNG", name="bild.png"):
    image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    image.paste(colour, (40, 40, 160, 160))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BadgeImageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def badge_with_image(self, name="Zahnrad"):
        badge = Badge(name=name)
        badge.set_image(process_badge_image(png()))
        badge.save()
        return badge

    def test_placeholder_without_image(self):
        badge = Badge.objects.create(name="Erster Roboter")
        self.assertIsNone(badge.image_url)

    def test_public_view_serves_only_the_current_badge_image(self):
        badge = self.badge_with_image()
        url = badge.image_url
        self.assertRegex(url, rf"^/badges/{badge.pk}/bild/[0-9a-f]{{32}}\.png$")

        response = self.client.get(url)  # no login: public profiles use it
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Content-Disposition"], "inline")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("immutable", response["Cache-Control"])
        image = Image.open(io.BytesIO(b"".join(response.streaming_content)))
        self.assertEqual(image.size, (512, 512))

        wrong = f"/badges/{badge.pk}/bild/{'0' * 32}.png"
        self.assertEqual(self.client.get(wrong).status_code, 404)
        self.assertEqual(self.client.post(url).status_code, 405)
        empty = Badge.objects.create(name="Leer")
        self.assertEqual(
            self.client.get(f"/badges/{empty.pk}/bild/{'0' * 32}.png").status_code, 404
        )

    def test_private_uploads_are_not_reachable_through_the_badge_view(self):
        badge = self.badge_with_image()
        for name in ("..%2Feinreichungen%2Fx", "einreichungen", "x.jpg"):
            response = self.client.get(f"/badges/{badge.pk}/bild/{name}.png")
            self.assertEqual(response.status_code, 404)

    def test_replacing_and_deleting_remove_the_old_file(self):
        badge = self.badge_with_image()
        old = badge.image_file.name
        storage = badge.image_file.storage
        with self.captureOnCommitCallbacks(execute=True):
            badge.set_image(process_badge_image(png((255, 0, 0, 255))))
            badge.save()
        self.assertFalse(storage.exists(old))
        self.assertTrue(storage.exists(badge.image_file.name))
        current = badge.image_file.name
        with self.captureOnCommitCallbacks(execute=True):
            badge.delete()
        self.assertFalse(storage.exists(current))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class BadgeAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coach = User.objects.create_user(
            "coach", password="Roboter-777", is_staff=True
        )
        group, _ = Group.objects.get_or_create(name=COACH_GROUP_NAME)
        cls.coach.groups.add(group)
        # The coach group gets its permissions from data migrations.
        cls.staff = User.objects.create_user(
            "staff", password="Roboter-777", is_staff=True
        )
        cls.staff.user_permissions.set(group.permissions.all())

    def post(self, data, badge=None):
        url = (
            reverse("admin:badges_badge_change", args=[badge.pk])
            if badge
            else reverse("admin:badges_badge_add")
        )
        return self.client.post(url, {"name": "Zahnrad", "description": "", **data})

    def test_form_shows_the_notice(self):
        self.client.force_login(self.coach)
        response = self.client.get(reverse("admin:badges_badge_add"))
        self.assertContains(response, "Keine Fotos von Personen hochladen")
        self.assertIn("öffentlich sichtbar", UPLOAD_NOTICE)
        self.assertContains(response, 'accept="image/png,image/webp"')

    def test_coach_uploads_png_and_webp(self):
        self.client.force_login(self.coach)
        for fmt, name in (("PNG", "a.png"), ("WEBP", "b.webp")):
            with self.subTest(fmt):
                Badge.objects.all().delete()
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.post({"upload": png(fmt=fmt, name=name)})
                self.assertEqual(response.status_code, 302)
                badge = Badge.objects.get()
                self.assertTrue(badge.image_file.name.startswith("badges/"))
                with badge.image_file.open("rb") as handle:
                    stored = Image.open(handle)
                    self.assertEqual((stored.format, stored.size), ("PNG", (512, 512)))

    def test_svg_and_jpeg_are_rejected(self):
        self.client.force_login(self.coach)
        svg = SimpleUploadedFile(
            "bild.png", b"<svg xmlns='http://www.w3.org/2000/svg'/>"
        )
        response = self.post({"upload": svg})
        self.assertContains(response, "kein lesbares PNG- oder WebP-Bild")
        jpeg = io.BytesIO()
        Image.new("RGB", (50, 50)).save(jpeg, format="JPEG")
        response = self.post({"upload": SimpleUploadedFile("x.jpg", jpeg.getvalue())})
        self.assertContains(response, "Erlaubt sind nur PNG und WebP")
        self.assertFalse(Badge.objects.exists())

    def test_coach_removes_the_image(self):
        self.client.force_login(self.coach)
        with self.captureOnCommitCallbacks(execute=True):
            self.post({"upload": png()})
        badge = Badge.objects.get()
        name = badge.image_file.name
        with self.captureOnCommitCallbacks(execute=True):
            self.post({"remove_image": "on"}, badge)
        badge.refresh_from_db()
        self.assertFalse(badge.image_file)
        self.assertFalse(badge.image_file.storage.exists(name))

    def test_staff_outside_the_coach_group_cannot_upload(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:badges_badge_add"))
        self.assertContains(response, "Nur Coaches können Bilder ändern.")
        response = self.post({"upload": png()})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Badge.objects.get().image_file)
