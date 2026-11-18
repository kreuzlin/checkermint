from django import template
from django.utils.safestring import mark_safe

from core.markdown import ImageRef, render_markdown
from core.private_files import private_file_url

register = template.Library()


@register.filter
def instructions_markdown(text, task):
    """Markdown of a task version with the task's own uploaded images.

    `{{ version.instructions|instructions_markdown:task }}`. Only images of
    this task become <img> tags; `mark_safe` is fine because
    `render_markdown` sanitises with an allow-list.
    """
    images = {
        image.pk: ImageRef(
            url=private_file_url("anleitungsbild", image),
            alt=image.alt_text,
            width=image.width,
            height=image.height,
        )
        for image in task.instruction_images.all()
    }
    return mark_safe(render_markdown(str(text or ""), images=images))
