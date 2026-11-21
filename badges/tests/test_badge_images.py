"""Processing of badge images and the move of the shipped set (ADR 0018, #120)."""

import importlib
import io
import shutil
import tempfile

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from badges.images import SIZE, process_badge_image
from badges.models import Badge

move = importlib.import_module("badges.migrations.0005_move_shipped_images")


def upload(
    fmt="PNG", size=(300, 200), name="bild.png", motif=(50, 40, 250, 160), **save
):
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.paste((0, 220, 173, 255), motif)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **save)
    return SimpleUploadedFile(name, buffer.getvalue())


def opened(content):
    return Image.open(io.BytesIO(content.read()))


class ProcessBadgeImageTests(SimpleTestCase):
    def test_png_and_webp_become_a_square_png(self):
        for fmt in ("PNG", "WEBP"):
            with self.subTest(fmt):
                result = opened(process_badge_image(upload(fmt)))
                self.assertEqual(result.format, "PNG")
                self.assertEqual(result.size, (SIZE, SIZE))
                self.assertEqual(result.mode, "RGBA")

    def test_motif_is_cropped_and_centred_at_85_percent(self):
        result = opened(process_badge_image(upload()))
        left, top, right, bottom = result.getchannel("A").getbbox()
        # Motif 200 × 120 → scaled to 435 × 261 (85 % of 512 on the long side).
        self.assertEqual(right - left, 435)
        self.assertAlmostEqual((left + right) / 2, SIZE / 2, delta=1)
        self.assertAlmostEqual((top + bottom) / 2, SIZE / 2, delta=1)

    def test_metadata_is_removed(self):
        exif = Image.Exif()
        exif[0x010E] = "Geheime Beschreibung"
        source = upload(exif=exif.tobytes(), pnginfo=None)
        result = opened(process_badge_image(source))
        self.assertFalse(result.getexif())
        self.assertNotIn("exif", result.info)
        self.assertNotIn(b"Geheime", process_badge_image(source).read())

    def test_other_formats_are_rejected(self):
        for fmt, name in (("JPEG", "bild.png"), ("GIF", "bild.gif")):
            with self.subTest(fmt):
                image = Image.new("RGB", (100, 100), "white")
                buffer = io.BytesIO()
                image.save(buffer, format=fmt)
                with self.assertRaisesMessage(ValidationError, "nur PNG und WebP"):
                    process_badge_image(SimpleUploadedFile(name, buffer.getvalue()))

    def test_svg_is_rejected_even_named_png(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with self.assertRaisesMessage(ValidationError, "kein lesbares"):
            process_badge_image(SimpleUploadedFile("bild.png", svg))

    def test_limits(self):
        with self.assertRaisesMessage(ValidationError, "höchstens 2 MB"):
            process_badge_image(
                SimpleUploadedFile("gross.png", b"x" * (2 * 1024 * 1024 + 1))
            )
        with self.assertRaisesMessage(ValidationError, "4096"):
            process_badge_image(upload(size=(4097, 10), motif=(0, 0, 10, 10)))
        with self.assertRaisesMessage(ValidationError, "durchsichtig"):
            process_badge_image(upload(motif=(0, 0, 0, 0)))


MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MoveShippedImagesTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_shipped_images_are_moved_into_the_upload(self):
        led = Badge.objects.create(name="Erste LED", image="erste-led.png")
        placeholder = Badge.objects.create(name="Ohne Bild")
        missing = Badge.objects.create(name="Fehlt", image="gibt-es-nicht.png")

        move.move_shipped_images(apps, None)

        led.refresh_from_db()
        self.assertTrue(led.image_file.name.startswith("badges/"))
        self.assertTrue(led.image_file.name.endswith(".png"))
        with led.image_file.open("rb") as handle:
            self.assertEqual(Image.open(handle).size, (SIZE, SIZE))
        self.assertEqual(led.image, "erste-led.png")  # unchanged until #120 part 2
        placeholder.refresh_from_db()
        missing.refresh_from_db()
        self.assertFalse(placeholder.image_file)
        self.assertFalse(missing.image_file)

        name = led.image_file.name
        move.move_shipped_images(apps, None)  # idempotent
        led.refresh_from_db()
        self.assertEqual(led.image_file.name, name)

        move.remove_uploaded_images(apps, None)
        led.refresh_from_db()
        self.assertFalse(led.image_file)
        self.assertFalse(led.image_file.storage.exists(name))
