"""Public badge images (ADR 0018).

The only upload that is public: badge images appear on public profiles. The
view serves nothing but the processed image stored on a Badge – it never
maps the URL to a file system path. The URL contains the random file name,
so it changes with every new upload and can be cached for a long time.
"""

from pathlib import PurePath

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe

from .models import Badge


@require_safe
def badge_image(request, pk, name):
    badge = get_object_or_404(Badge, pk=pk)
    if not badge.image_file or PurePath(badge.image_file.name).stem != name:
        raise Http404
    response = FileResponse(badge.image_file.open("rb"), content_type="image/png")
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
