"""Processing of uploaded badge images (ADR 0018, #120)."""

import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from badges.images import SIZE, process_badge_image


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
