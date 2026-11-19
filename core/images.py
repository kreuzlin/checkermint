"""Decode, clean and re-encode uploaded images (ADR 0009, brief 4.3).

Re-encoding is the guarantee that metadata (EXIF incl. GPS, XMP, comments)
is gone: only the pixels are kept. Uploads that Pillow cannot decode are
rejected.
"""

import io
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_EDGE = 2000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Refuse decompression bombs early (about 50 megapixels).
MAX_PIXELS = 50_000_000
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class ProcessedImage:
    content: ContentFile
    extension: str
    width: int
    height: int


def process_image(uploaded, max_edge: int = MAX_EDGE) -> ProcessedImage:
    """Return the image re-encoded without metadata, at most `max_edge` px."""
    if uploaded.size and uploaded.size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            "Das Bild ist zu gross (höchstens %(mb)d MB).",
            params={"mb": MAX_UPLOAD_BYTES // (1024 * 1024)},
        )
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as source:
            if source.format not in ACCEPTED_FORMATS:
                raise ValidationError("Erlaubt sind JPEG, PNG und WebP.")
            if source.width * source.height > MAX_PIXELS:
                raise ValidationError("Das Bild hat zu viele Pixel.")
            image = ImageOps.exif_transpose(source)
            image.load()
    except UnidentifiedImageError, OSError, Image.DecompressionBombError:
        raise ValidationError("Diese Datei ist kein lesbares Bild.") from None

    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    has_alpha = image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    )
    buffer = io.BytesIO()
    image = image.convert("RGBA" if has_alpha else "RGB")
    # Drop everything but pixels: Pillow would otherwise write some info
    # entries (e.g. EXIF, ICC profile, PNG text) back into the new file.
    image.info = {}
    if has_alpha:
        image.save(buffer, format="PNG", optimize=True)
        extension = ".png"
    else:
        image.save(buffer, format="JPEG", quality=85, optimize=True)
        extension = ".jpg"
    return ProcessedImage(
        content=ContentFile(buffer.getvalue()),
        extension=extension,
        width=image.width,
        height=image.height,
    )
