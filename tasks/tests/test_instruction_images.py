"""Images in task instructions (brief 5.3/5.4, ADR 0009/0010, issue #18)."""

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
from core.private_files import private_file_url
from tasks.models import (
    InstructionImage,
    PublishedVersionError,
    Task,
    TaskRequirement,
    TaskVersion,
    Topic,
)

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def jpeg_bytes(size=(60, 30)):
    image = Image.new("RGB", size, "blue")
    exif = Image.Exif()
    exif[0x8825] = {2: (47.0, 22.0, 0.0)}
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class InstructionImageTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.topic = Topic.objects.create(name="Code", slug="code")
        self.task = Task.objects.create(topic=self.topic, slug="linienfolger")
        self.coach = User.objects.create_user(
            "coach", password="Roboter-777", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.participant = User.objects.create_user("kind", password="Roboter-77")

    def make_image(self, alt="Sensor von unten"):
        image = InstructionImage(task=self.task, alt_text=alt)
        image.image.save("bild.jpg", SimpleUploadedFile("bild.jpg", jpeg_bytes()))
        return image

    def make_version(self, instructions, publish=True):
        version = TaskVersion.objects.create(
            task=self.task, title="Linienfolger", instructions=instructions
        )
        TaskRequirement.objects.create(
            task_version=version, key="text", type="text", label="Text"
        )
        if publish:
            version.publish()
            self.task.is_published = True
            self.task.save()
        return version


class ImmutabilityTests(InstructionImageTestCase):
    def test_reference_and_random_storage_name(self):
        image = self.make_image()
        self.assertEqual(image.reference, f"![Sensor von unten](bild:{image.pk})")
        self.assertRegex(image.image.name, r"^anleitungen/[0-9a-f]{32}\.jpg$")

    def test_used_image_cannot_be_deleted_or_changed(self):
        image = self.make_image()
        self.make_version(f"Siehe ![x](bild:{image.pk})")
        self.assertTrue(image.used_by_published_version())
        with self.assertRaises(PublishedVersionError):
            image.delete()
        image.alt_text = "Neu"
        with self.assertRaises(PublishedVersionError):
            image.save()

    def test_file_cannot_be_replaced(self):
        image = self.make_image()
        image.image.name = "anleitungen/anderes.jpg"
        with self.assertRaises(PublishedVersionError):
            image.save()

    def test_unused_image_can_be_deleted_with_its_file(self):
        image = self.make_image()
        self.make_version("Ohne Bild, mit bild:999 im Text")
        storage, name = image.image.storage, image.image.name
        image.delete()
        self.assertFalse(storage.exists(name))


class AccessTests(InstructionImageTestCase):
    def get(self, image, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get(private_file_url("anleitungsbild", image))

    def test_participant_sees_image_of_published_version(self):
        image = self.make_image()
        self.make_version(f"![x](bild:{image.pk})")
        response = self.get(image, self.participant)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertIn("private", response["Cache-Control"])

    def test_anonymous_gets_404(self):
        image = self.make_image()
        self.make_version(f"![x](bild:{image.pk})")
        self.assertEqual(self.get(image).status_code, 404)

    def test_draft_only_images_only_for_coaches(self):
        image = self.make_image()
        self.make_version(f"![x](bild:{image.pk})", publish=False)
        self.assertEqual(self.get(image, self.participant).status_code, 404)
        self.assertEqual(self.get(image, self.coach).status_code, 200)

    def test_hidden_or_archived_task_hides_images(self):
        image = self.make_image()
        self.make_version(f"![x](bild:{image.pk})")
        self.task.is_archived = True
        self.task.save()
        self.assertEqual(self.get(image, self.participant).status_code, 404)


class RenderingTests(InstructionImageTestCase):
    def test_preview_renders_own_images_only(self):
        image = self.make_image()
        other_task = Task.objects.create(topic=self.topic, slug="andere")
        other = InstructionImage(task=other_task, alt_text="Fremd")
        other.image.save("b.jpg", SimpleUploadedFile("b.jpg", jpeg_bytes()))
        version = self.make_version(
            f"![a](bild:{image.pk}) ![b](bild:{other.pk})", publish=False
        )
        self.client.force_login(self.coach)
        response = self.client.get(
            reverse("admin:tasks_taskversion_preview", args=[version.pk])
        )
        self.assertContains(
            response,
            f'src="/dateien/anleitungsbild/{image.pk}/" alt="Sensor von unten"',
        )
        self.assertNotContains(response, f"/dateien/anleitungsbild/{other.pk}/")
        self.assertContains(response, "[Bild fehlt]")


class AdminUploadTests(InstructionImageTestCase):
    def post_task(self, image_data):
        data = {
            "topic": self.topic.pk,
            "slug": "linienfolger",
            "order": 0,
            "min_level": 1,
            "instruction_images-TOTAL_FORMS": 1,
            "instruction_images-INITIAL_FORMS": 0,
            "instruction_images-MIN_NUM_FORMS": 0,
            "instruction_images-MAX_NUM_FORMS": 1000,
            "instruction_images-0-alt_text": "Sensor",
            "instruction_images-0-image": image_data,
            "versions-TOTAL_FORMS": 0,
            "versions-INITIAL_FORMS": 0,
            "versions-MIN_NUM_FORMS": 0,
            "versions-MAX_NUM_FORMS": 1000,
        }
        self.client.force_login(self.coach)
        return self.client.post(
            reverse("admin:tasks_task_change", args=[self.task.pk]), data
        )

    def test_coach_uploads_cleaned_image(self):
        upload = SimpleUploadedFile(
            "Foto von Anna.jpg", jpeg_bytes((3000, 100)), "image/jpeg"
        )
        response = self.post_task(upload)
        self.assertEqual(response.status_code, 302)
        image = InstructionImage.objects.get()
        self.assertEqual(image.original_filename, "Foto von Anna.jpg")
        self.assertEqual(image.uploaded_by, self.coach)
        self.assertEqual(image.width, 2000)
        self.assertNotIn("Anna", image.image.name)
        with image.image.open("rb") as stored, Image.open(stored) as cleaned:
            self.assertEqual(len(cleaned.getexif()), 0)

    def test_non_image_is_rejected(self):
        response = self.post_task(SimpleUploadedFile("x.jpg", b"kein bild"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InstructionImage.objects.exists())

    def test_task_page_shows_reference_to_copy(self):
        image = self.make_image()
        self.client.force_login(self.coach)
        response = self.client.get(
            reverse("admin:tasks_task_change", args=[self.task.pk])
        )
        self.assertContains(response, f"![Sensor von unten](bild:{image.pk})")
        self.assertNotContains(response, "ß")
