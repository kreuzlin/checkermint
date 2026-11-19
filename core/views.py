import mimetypes
from pathlib import PurePath

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from accounts.roles import is_coach
from badges.awards import recent_badges
from submissions.dashboard import dashboard
from submissions.queue import SUBMISSION, queue_entries

from . import private_files
from .seo import SeoMixin


class HomeView(SeoMixin, TemplateView):
    """Visitors: the public start page (landing page, #45). Participants:
    their dashboard (brief 5.9). Coaches: the queue and the badge feed."""

    template_name = "core/home.html"
    # No page title: the home page uses the plain site title.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if not user.is_authenticated:
            return context
        # Logged-in users only: nicknames are not public (brief 4, 5.9).
        if is_coach(user):
            context["is_coach"] = True
            entries = queue_entries()
            context["queue_size"] = len(entries)
            context["queue_submissions"] = sum(e.kind == SUBMISSION for e in entries)
            context["queue_hints"] = len(entries) - context["queue_submissions"]
            context["recent_badges"] = recent_badges()
        else:
            context["dashboard"] = dashboard(user)
            context["recent_badges"] = context["dashboard"].recent_badges
        return context


def version(request):
    """Commit of the running build, e.g. to compare the live site with main."""
    commit = settings.APP_COMMIT
    response = JsonResponse({"commit": commit, "short": commit[:7]})
    response["Cache-Control"] = "no-store"
    return response


def robots_txt(request):
    """Disallow all crawlers everywhere; there is no sitemap (brief, 4.7)."""
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


@require_GET
def private_file(request, kind, pk, variant=None):
    """Stream a private upload after the per-object access check (ADR 0009).

    Unknown kinds, missing objects or files and missing access all answer
    404, so the response does not reveal whether a file exists.
    """
    file_kind = private_files.get_kind(kind)
    if file_kind is None:
        raise Http404
    obj = file_kind.model._default_manager.filter(pk=pk).first()
    if obj is None or not file_kind.can_access(request.user, obj):
        raise Http404
    stored = file_kind.get_file(obj, variant)
    if not stored or not stored.name:
        raise Http404
    try:
        handle = stored.storage.open(stored.name, "rb")
    except FileNotFoundError:
        raise Http404 from None

    filename = file_kind.get_filename(obj) if file_kind.get_filename else None
    filename = filename or PurePath(stored.name).name
    if file_kind.inline:
        content_type = (
            mimetypes.guess_type(stored.name)[0] or "application/octet-stream"
        )
    else:
        content_type = "application/octet-stream"
    response = FileResponse(
        handle,
        as_attachment=not file_kind.inline,
        filename=filename,
        content_type=content_type,
    )
    response["Cache-Control"] = file_kind.cache_control
    response["X-Content-Type-Options"] = "nosniff"
    if file_kind.inline:
        # Even our own images must not run scripts or be framed elsewhere.
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
