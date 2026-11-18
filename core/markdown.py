"""Markdown rendering with HTML sanitising (brief, 8.8).

Rich text written by coaches and participants (task instructions, feedback,
"about me") is Markdown. It is converted to HTML and then cleaned with an
allow-list, so raw HTML, scripts, event handlers and unsafe links never
reach the page. Use it only through the `|markdown` template filter.

Images are not allowed yet: an external image URL would make the browser
contact a third party (brief, 4.9). Instruction images come with their own
issue and will be restricted to our own private media URLs.
"""

import markdown as markdown_lib
import nh3

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


def render_markdown(text: str) -> str:
    """Return sanitised HTML for a Markdown string (empty for empty input)."""
    if not text:
        return ""
    html = markdown_lib.markdown(text, extensions=EXTENSIONS, output_format="html")
    for old, new in HEADING_SHIFT.items():
        html = html.replace(old, new)
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )
