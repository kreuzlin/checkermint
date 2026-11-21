"""Badge images: check, clean and normalise an uploaded image (ADR 0018).

Badge images are public (public profiles), so they go through stricter
rules than other uploads: only PNG and WebP (detected by decoding, never by
the file name; no SVG), small limits, and the result is always our own PNG
with pixels only. The visible motif is cropped and centred so that every
badge looks equally large.
"""

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

ACCEPTED_FORMATS = {"PNG", "WEBP"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_EDGE_IN = 4096
SIZE = 512
# Share of the height the visible motif fills.
FILL = 0.85
# Alpha above which a pixel counts as part of the motif (ignores faint glow).
ALPHA_THRESHOLD = 20


def process_badge_image(uploaded) -> ContentFile:
    """Return the cleaned 512 px PNG of an upload; raises ValidationError."""
    if uploaded.size and uploaded.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Das Bild ist zu gross (höchstens 2 MB).")
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as source:
            if source.format not in ACCEPTED_FORMATS:
                raise ValidationError("Erlaubt sind nur PNG und WebP.")
            if source.width > MAX_EDGE_IN or source.height > MAX_EDGE_IN:
                raise ValidationError(
                    "Das Bild ist zu gross (höchstens 4096 × 4096 Pixel)."
                )
            image = source.convert("RGBA")
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        raise ValidationError(
            "Diese Datei ist kein lesbares PNG- oder WebP-Bild."
        ) from None
    return ContentFile(_encode(_normalise(image)), name="badge.png")


def _normalise(image: Image.Image) -> Image.Image:
    """Crop to the visible motif and centre it at FILL on a SIZE square."""
    mask = image.getchannel("A").point(
        lambda value: 255 if value > ALPHA_THRESHOLD else 0
    )
    box = mask.getbbox()
    if box is None:
        raise ValidationError("Das Bild ist vollständig durchsichtig.")
    motif = image.crop(box)
    scale = FILL * SIZE / max(motif.width, motif.height)
    motif = motif.resize(
        (max(1, round(motif.width * scale)), max(1, round(motif.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (SIZE, SIZE))
    canvas.paste(motif, ((SIZE - motif.width) // 2, (SIZE - motif.height) // 2))
    return canvas


def _encode(image: Image.Image) -> bytes:
    """PNG with pixels only: no EXIF, XMP, text chunks or ICC profile."""
    image.info = {}
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
