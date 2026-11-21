from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html

from submissions.handlers import handler_for
from tasks.models import SimulatorConfig, TaskRequirement
from tasks.simulator import COMPLETION_CODE_KEY, codes_match

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


@register.simple_tag(takes_context=True)
def code_check(context, item):
    """ "Code stimmt" / "Code stimmt nicht" next to a completion code, for
    coaches on the review page only (ADR 0021). Shows the expected code,
    which participants never see; the coach still decides."""
    requirement = item.requirement
    if not context.get("show_code_check"):
        return ""
    if (
        requirement.key != COMPLETION_CODE_KEY
        or requirement.type != TaskRequirement.Type.TEXT
    ):
        return ""
    config = SimulatorConfig.objects.filter(
        task_version_id=requirement.task_version_id
    ).first()
    if config is None or not config.expected_code:
        return ""
    if codes_match(item.text, config.expected_code):
        return format_html(
            '<p class="code-check code-check-ok"><span aria-hidden="true">✓</span> '
            "Code stimmt</p>"
        )
    return format_html(
        '<p class="code-check code-check-wrong"><span aria-hidden="true">✗</span> '
        "<strong>Code stimmt nicht</strong> – erwartet: <code>{}</code></p>",
        config.expected_code,
    )
