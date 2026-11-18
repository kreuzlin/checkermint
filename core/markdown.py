"""Markdown rendering with HTML sanitising (brief, 8.8).

Rich text written by coaches and participants (task instructions, feedback,
"about me") is Markdown. It is converted to HTML and then cleaned with an
allow-list, so raw HTML, scripts, event handlers and unsafe links never
reach the page. Use it only through the `|markdown` template filter.

External images are never allowed: they would make the browser contact a
third party (brief, 4.9). Task instructions may embed their own uploaded
images as `![Beschreibung](bild:12)`; the caller passes the images it
allows (`images`), and only those become `<img>` tags pointing to our
private file view.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

import markdown as markdown_lib
import nh3
from django.utils.html import format_html

EXTENSIONS = ["fenced_code", "tables", "sane_lists"]

ALLOWED_TAGS = {
    "p", "br", "hr",
    "h2", "h3", "h4",
    "strong", "em", "code", "pre", "blockquote",
    "ul", "ol", "li",
    "a",
    "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "th": {"align"},
    "td": {"align"},
}

# Relative links (e.g. "/aufgaben/…") stay allowed; nh3 only checks schemes
# of absolute URLs.
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

# Headings start at h2: the page title is the only h1.
HEADING_SHIFT = {"<h1>": "<h2>", "</h1>": "</h2>"}


# Reference to an uploaded image in Markdown: ![…](bild:12)
IMAGE_SCHEME = "bild"
IMG_TAG = re.compile(r"<img\b[^>]*>")
IMAGE_SRC = re.compile(r'\bsrc="bild:(\d+)"')


@dataclass(frozen=True)
class ImageRef:
    """An image the caller allows in this text."""

    url: str
    alt: str
    width: int | None = None
    height: int | None = None


def render_markdown(text: str, images: Mapping[int, ImageRef] | None = None) -> str:
    """Return sanitised HTML for a Markdown string (empty for empty input).

    `images` maps image ids to the images allowed in this text; without it,
    images are removed entirely.
    """
    if not text:
        return ""
    html = markdown_lib.markdown(text, extensions=EXTENSIONS, output_format="html")
    for old, new in HEADING_SHIFT.items():
        html = html.replace(old, new)
    tags, attributes, schemes = ALLOWED_TAGS, ALLOWED_ATTRIBUTES, ALLOWED_URL_SCHEMES
    if images is not None:
        tags = tags | {"img"}
        attributes = {**attributes, "img": {"src"}}
        schemes = schemes | {IMAGE_SCHEME}
    html = nh3.clean(
        html,
        tags=tags,
        attributes=attributes,
        url_schemes=schemes,
        link_rel="noopener noreferrer nofollow",
    )
    if images is not None:
        html = IMG_TAG.sub(lambda match: _image_tag(match.group(0), images), html)
    return html


def _image_tag(tag: str, images: Mapping[int, ImageRef]) -> str:
    """Replace a sanitised <img> with our own tag, or a note if not allowed."""
    match = IMAGE_SRC.search(tag)
    image = images.get(int(match.group(1))) if match else None
    if image is None:
        return '<span class="missing-image">[Bild fehlt]</span>'
    if image.width and image.height:
        return format_html(
            '<img src="{}" alt="{}" width="{}" height="{}" loading="lazy">',
            image.url,
            image.alt,
            image.width,
            image.height,
        )
    return format_html('<img src="{}" alt="{}" loading="lazy">', image.url, image.alt)
