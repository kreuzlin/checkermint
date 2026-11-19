"""Decode, clean and re-encode uploaded images (ADR 0009, brief 4.3, 5.7).

Re-encoding is the guarantee that metadata (EXIF incl. GPS, XMP, comments)
is gone: only the pixels are kept. Uploads that Pillow cannot decode are
rejected. HEIC/HEIF photos (iPhones) are decoded with `pillow-heif` and
stored as JPEG.
"""

import io
from dataclasses import dataclass

import pillow_heif
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

pillow_heif.register_heif_opener()

MAX_EDGE = 2000
THUMBNAIL_EDGE = 400
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# Refuse decompression bombs early (about 50 megapixels).
MAX_PIXELS = 50_000_000
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}


@dataclass(frozen=True)
class ProcessedImage:
    content: ContentFile
    extension: str
    width: int
    height: int


def decode_image(uploaded, max_bytes: int = MAX_UPLOAD_BYTES) -> Image.Image:
    """Open, check and auto-rotate an upload; raises ValidationError."""
    if uploaded.size and uploaded.size > max_bytes:
        raise ValidationError(
            "Das Bild ist zu gross (höchstens %(mb)d MB).",
            params={"mb": max_bytes // (1024 * 1024)},
        )
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as source:
            if source.format not in ACCEPTED_FORMATS:
                raise ValidationError("Erlaubt sind JPEG, PNG, HEIC und WebP.")
            if source.width * source.height > MAX_PIXELS:
                raise ValidationError("Das Bild hat zu viele Pixel.")
            image = ImageOps.exif_transpose(source)
            image.load()
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        raise ValidationError("Diese Datei ist kein lesbares Bild.") from None
    return image


def encode_image(image: Image.Image, max_edge: int = MAX_EDGE) -> ProcessedImage:
    """Resize to at most `max_edge` px and re-encode with pixels only."""
    image = image.copy()
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


def process_image(
    uploaded, max_edge: int = MAX_EDGE, max_bytes: int = MAX_UPLOAD_BYTES
) -> ProcessedImage:
    """Return the image re-encoded without metadata, at most `max_edge` px."""
    return encode_image(decode_image(uploaded, max_bytes), max_edge)


def process_photo(
    uploaded, max_bytes: int = MAX_UPLOAD_BYTES
) -> tuple[ProcessedImage, ProcessedImage]:
    """A photo and its thumbnail, both without metadata (one decode)."""
    image = decode_image(uploaded, max_bytes)
    return encode_image(image, MAX_EDGE), encode_image(image, THUMBNAIL_EDGE)
