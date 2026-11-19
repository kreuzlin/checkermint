"""Generate the web assets of the logo from the originals in design/logo/.

Run from the repository root after changing an original:

    uv run python design/generate_assets.py

Writes into core/static/core/brand/ (committed, collected into the image):

- logo-header.svg   wide logo for the dark header
- icon.svg          square icon, also used as the SVG favicon
- favicon-32.png    PNG favicon for browsers without SVG favicons
- apple-touch-icon.png (180 px) for iOS home screens

The SVGs are cleaned: editor metadata (Inkscape/Sodipodi) is removed, the
drawing itself is unchanged. PNGs are resized from the 512 px icon and saved
without metadata. Never edit the generated files by hand.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "design" / "logo"
TARGET = ROOT / "core" / "static" / "core" / "brand"

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


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for source_name, target_name in SVGS.items():
        clean_svg(SOURCE / source_name, TARGET / target_name)
        print(f"wrote {TARGET / target_name}")
    for target_name, size in PNGS.items():
        resize_icon(SOURCE / "CHECKERMINT_Icon_512.png", TARGET / target_name, size)
        print(f"wrote {TARGET / target_name}")


if __name__ == "__main__":
    main()
