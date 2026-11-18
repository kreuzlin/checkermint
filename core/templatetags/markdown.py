from django import template
from django.utils.safestring import mark_safe

from core.markdown import render_markdown

register = template.Library()


@register.filter(name="markdown")
def markdown_filter(value):
    """Render Markdown as sanitised HTML: `{{ task.instructions|markdown }}`.

    `mark_safe` is fine here because `render_markdown` cleans the HTML with
    an allow-list; never mark user content safe anywhere else.
    """
    return mark_safe(render_markdown(str(value or "")))
