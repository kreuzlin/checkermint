from django import template
from django.template.loader import render_to_string

from submissions.handlers import handler_for

register = template.Library()


@register.simple_tag
def submission_item(item):
    """The item rendered by its type's handler (ADR 0011)."""
    handler = handler_for(item.requirement)
    if handler is None:
        return ""
    return render_to_string(handler.display_template, handler.render(item))
