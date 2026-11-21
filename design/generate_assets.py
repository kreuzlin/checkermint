"""Generate the web assets from the originals in design/.

Run from the repository root after changing an original:

    uv run python design/generate_assets.py

Writes into core/static/core/brand/ (committed, collected into the image):

- logo-header.svg   wide logo for the dark header
- icon.svg          square icon, also used as the SVG favicon
- favicon-32.png    PNG favicon for browsers without SVG favicons
- apple-touch-icon.png (180 px) for iOS home screens

and badge images from design/badges/ into badges/static/badges/img/
(offered in the badge admin): PNGs resized to BADGE_SIZE px, SVGs cleaned.
PNG badges are normalised first: the visible motif is cropped and centred
so that it fills BADGE_FILL of the height, so badges delivered at different
sizes or margins look the same size next to each other.
The web name is the original's name without a leading number, in lower
case with hyphens, e.g. "01_Erste_LED.png" -> "erste-led.png".

The SVGs are cleaned: editor metadata (Inkscape/Sodipodi) is removed, the
drawing itself is unchanged. PNGs are resized from the 512 px icon and saved
without metadata. Never edit the generated files by hand.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "design" / "logo"
TARGET = ROOT / "core" / "static" / "core" / "brand"
BADGE_SOURCE = ROOT / "design" / "badges"
BADGE_TARGET = ROOT / "badges" / "static" / "badges" / "img"
# 512 px: the data migration badges/0005 moves these into the uploaded
# badge images (ADR 0018), which are 512 px; shown at 40-48 px.
BADGE_SIZE = 512
# Share of the height the visible motif fills (as in the first badge set).
BADGE_FILL = 0.85
# Alpha above which a pixel counts as part of the motif (ignores faint glow).
BADGE_ALPHA_THRESHOLD = 20

SVG_NS = "http://www.w3.org/2000/svg"
EDITOR_NAMESPACES = (
    "http://www.inkscape.org/namespaces/inkscape",
    "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
)

SVGS = {
    "CHECKERMINT_Header.svg": "logo-header.svg",
    "CHECKERMINT_Icon.svg": "icon.svg",
}

PNGS = {
    "favicon-32.png": 32,
    "apple-touch-icon.png": 180,
}


def _is_editor_name(name):
    return any(name.startswith("{" + ns + "}") for ns in EDITOR_NAMESPACES)


def clean_svg(source, target):
    """Copy an SVG without editor elements and attributes."""
    ET.register_namespace("", SVG_NS)
    tree = ET.parse(source)
    for parent in tree.iter():
        for child in list(parent):
            if _is_editor_name(child.tag):
                parent.remove(child)
        for attr in [a for a in parent.attrib if _is_editor_name(a)]:
            del parent.attrib[attr]
    tree.write(target, encoding="utf-8", xml_declaration=False)


def resize_icon(source, target, size):
    """Resize the square icon; saved without any metadata."""
    with Image.open(source) as image:
        image = image.convert("RGBA")
        if image.size != (size, size):
            image = image.resize((size, size), Image.Resampling.LANCZOS)
        clean = Image.new("RGBA", image.size)
        clean.paste(image)
        clean.save(target, format="PNG", optimize=True)


def badge_web_name(source):
    """'01_Erste_LED.png' -> 'erste-led.png'."""
    stem = re.sub(r"^\d+[_\- ]*", "", source.stem)
    stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return f"{stem}{source.suffix.lower()}"


def normalised_badge(source, size):
    """Crop to the visible motif, centre it at BADGE_FILL, resize to size."""
    with Image.open(source) as image:
        image = image.convert("RGBA")
    mask = image.getchannel("A").point(
        lambda value: 255 if value > BADGE_ALPHA_THRESHOLD else 0
    )
    box = mask.getbbox()
    if box is None:
        raise ValueError(f"{source.name}: image is fully transparent")
    motif = image.crop(box)
    scale = BADGE_FILL * size / max(motif.width, motif.height)
    motif = motif.resize(
        (max(1, round(motif.width * scale)), max(1, round(motif.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size))
    canvas.paste(motif, ((size - motif.width) // 2, (size - motif.height) // 2))
    return canvas


def badge_images():
    """Write the web versions of the badge originals."""
    BADGE_TARGET.mkdir(parents=True, exist_ok=True)
    for source in sorted(BADGE_SOURCE.glob("*")):
        suffix = source.suffix.lower()
        target = BADGE_TARGET / badge_web_name(source)
        if suffix == ".svg":
            clean_svg(source, target)
        elif suffix in {".png", ".webp"}:
            image = normalised_badge(source, BADGE_SIZE)
            image.save(target, format="PNG", optimize=True)
        else:
            continue
        print(f"wrote {target}")


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in SVGS.items():
        clean_svg(SOURCE / source_name, TARGET / target_name)
        print(f"wrote {TARGET / target_name}")
    for target_name, size in PNGS.items():
        resize_icon(SOURCE / "CHECKERMINT_Icon_512.png", TARGET / target_name, size)
        print(f"wrote {TARGET / target_name}")
    badge_images()


if __name__ == "__main__":
    main()
