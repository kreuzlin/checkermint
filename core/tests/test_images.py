"""Image cleaning on upload (ADR 0009, brief 4.3)."""

import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from core.images import process_image


def jpeg_with_gps(size=(3000, 1500), orientation=None):
    image = Image.new("RGB", size, "red")
    exif = Image.Exif()
    exif[0x010F] = "Kamera AG"  # Make
    exif[0x8825] = {2: (47.0, 22.0, 0.0), 4: (8.0, 32.0, 0.0)}  # GPS
    if orientation:
        exif[0x0112] = orientation
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return SimpleUploadedFile("foto.jpg", buffer.getvalue(), "image/jpeg")


class ProcessImageTests(SimpleTestCase):
    def test_metadata_is_removed_and_size_limited(self):
        result = process_image(jpeg_with_gps())
        self.assertEqual(result.extension, ".jpg")
        self.assertEqual((result.width, result.height), (2000, 1000))
        with Image.open(io.BytesIO(result.content.read())) as cleaned:
            self.assertEqual(len(cleaned.getexif()), 0)
            self.assertNotIn("exif", cleaned.info)
        self.assertNotIn(b"Kamera AG", result.content.read())

    def test_orientation_is_applied(self):
        # Orientation 6: rotate 90° clockwise for display.
        result = process_image(jpeg_with_gps(size=(400, 200), orientation=6))
        self.assertEqual((result.width, result.height), (200, 400))

    def test_transparent_png_stays_png(self):
        buffer = io.BytesIO()
        Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(buffer, format="PNG")
        upload = SimpleUploadedFile("x.png", buffer.getvalue(), "image/png")
        self.assertEqual(process_image(upload).extension, ".png")

    def test_non_images_and_other_formats_are_rejected(self):
        with self.assertRaisesMessage(ValidationError, "kein lesbares Bild"):
            process_image(SimpleUploadedFile("x.jpg", b"<script>alert(1)</script>"))
        buffer = io.BytesIO()
        Image.new("RGB", (5, 5)).save(buffer, format="GIF")
        with self.assertRaisesMessage(ValidationError, "JPEG, PNG und WebP"):
            process_image(SimpleUploadedFile("x.gif", buffer.getvalue()))

    def test_too_large_upload_is_rejected(self):
        upload = SimpleUploadedFile("x.jpg", b"0" * (10 * 1024 * 1024 + 1))
        with self.assertRaisesMessage(ValidationError, "zu gross"):
            process_image(upload)
