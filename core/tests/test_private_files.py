"""Private uploads through the access-checked view (ADR 0009, issue #21)."""

import shutil
import tempfile
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse

from core import private_files
from core.private_files import PrivateFileKind, RandomUploadPath, private_file_url

User = get_user_model()

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01"
    b"\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


class RandomUploadPathTests(TestCase):
    def test_random_name_keeps_only_a_safe_extension(self):
        upload_to = RandomUploadPath("einreichungen")
        path = upload_to(None, "Mein Roboter von Anna.JPG")
        self.assertRegex(path, r"^einreichungen/[0-9a-f]{32}\.jpg$")
        self.assertNotIn("Anna", path)
        self.assertRegex(upload_to(None, "x.ph p"), r"^einreichungen/[0-9a-f]{32}$")
        self.assertNotEqual(upload_to(None, "a.png"), upload_to(None, "a.png"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PrivateFileViewTests(TestCase):
    """Uses users as stand-in owner objects with a file per user."""

    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user("anna", password="Roboter-77")
        self.other = User.objects.create_user("ben", password="Roboter-77")
        self.stored = default_storage.save(
            "test/" + "a" * 32 + ".png", ContentFile(PNG)
        )
        self.addCleanup(default_storage.delete, self.stored)
        stored = self.stored

        def get_file(obj, variant):
            if variant not in (None, "vorschau"):
                return None
            # Stand-in for a FieldFile: the view only uses name and storage.
            return SimpleNamespace(name=stored, storage=default_storage)

        for name, inline in (("test-bild", True), ("test-datei", False)):
            private_files.register(
                name,
                PrivateFileKind(
                    model=User,
                    get_file=get_file,
                    can_access=lambda user, obj: (
                        user.is_authenticated and user.pk == obj.pk
                    ),
                    inline=inline,
                    get_filename=lambda obj: "roboter.png",
                ),
            )
            self.addCleanup(private_files.unregister, name)

    def get(self, kind="test-bild", obj=None, variant=None):
        return self.client.get(private_file_url(kind, obj or self.owner, variant))

    def test_owner_gets_inline_image_with_headers(self):
        self.client.force_login(self.owner)
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PNG)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_other_kinds_download_as_octet_stream(self):
        self.client.force_login(self.owner)
        response = self.get("test-datei")
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn(
            'attachment; filename="roboter.png"', response["Content-Disposition"]
        )

    def test_anonymous_and_foreign_users_get_404(self):
        self.assertEqual(self.get().status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.get().status_code, 404)
        self.assertEqual(self.get("test-datei").status_code, 404)

    def test_unknown_kind_object_variant_or_file_give_404(self):
        self.client.force_login(self.owner)
        url = reverse("core:private_file", kwargs={"kind": "gibts-nicht", "pk": 1})
        self.assertEqual(self.client.get(url).status_code, 404)
        url = reverse("core:private_file", kwargs={"kind": "test-bild", "pk": 999999})
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.get(variant="gross").status_code, 404)
        self.assertEqual(self.get(variant="vorschau").status_code, 200)
        default_storage.delete(self.stored)
        self.assertEqual(self.get().status_code, 404)

    def test_only_get(self):
        self.client.force_login(self.owner)
        url = private_file_url("test-bild", self.owner)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_url_contains_no_file_path(self):
        url = private_file_url("test-bild", self.owner)
        self.assertEqual(url, f"/dateien/test-bild/{self.owner.pk}/")
        self.assertNotIn(".png", url)

    def test_register_conflict(self):
        with self.assertRaises(ValueError):
            private_files.register(
                "test-bild",
                PrivateFileKind(model=User, get_file=None, can_access=None),
            )
