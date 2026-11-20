from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html

from submissions.handlers import handler_for

register = template.Library()


@register.simple_tag
def submission_item(item):
    """The item rendered by its type's handler (ADR 0011)."""
    handler = handler_for(item.requirement)
    if handler is None:
        return ""
    return render_to_string(handler.display_template, handler.render(item))


@register.simple_tag
def item_origin(item):
    """ "hochgeladen von …" when a coach added the item, "per Handy" for
    phone uploads, nothing for the participant's own uploads (#77).
    Internal pages only: the form, task page, history and review."""
    if item.added_by_someone_else:
        profile = getattr(item.uploaded_by, "profile", None)
        name = profile.nickname if profile else item.uploaded_by.get_username()
        return format_html('<span class="help">hochgeladen von Coach {}</span>', name)
    if item.via_phone:
        return format_html('<span class="help">per Handy hochgeladen</span>')
    return ""
