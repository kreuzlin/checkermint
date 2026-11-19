from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from accounts.mixins import CoachRequiredMixin
from accounts.views import participant_profiles
from core.seo import SeoMixin

from .matrix import progress_matrix, topics_with_tasks
from .participant import participant_detail


class ProgressMatrixView(CoachRequiredMixin, SeoMixin, TemplateView):
    """Coach: participants × tasks with the status per cell (brief 5.10.2)."""

    template_name = "overviews/progress_matrix.html"
    page_title = "Fortschritt"
    meta_description = "Wer welche Aufgabe gelöst, eingereicht oder begonnen hat."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topics = list(topics_with_tasks())
        slug = self.request.GET.get("thema", "")
        topic = next((t for t in topics if t.slug == slug), None)
        context.update(topics=topics, topic=topic, matrix=progress_matrix(topic))
        return context


class ParticipantDetailView(CoachRequiredMixin, SeoMixin, TemplateView):
    """Coach: one participant's levels, submissions, hint requests and
    suggested next tasks (brief 5.10.3, #40)."""

    template_name = "overviews/participant_detail.html"
    meta_description = "Level, Einreichungen und Hinweis-Anfragen einer Person."

    def get(self, request, *args, **kwargs):
        # After CoachRequiredMixin.dispatch: participants get 403, not 404.
        self.profile = get_object_or_404(
            participant_profiles(), nickname__iexact=kwargs["nickname"]
        )
        return super().get(request, *args, **kwargs)

    def get_page_title(self):
        return f"Fortschritt: {self.profile.nickname}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail"] = participant_detail(self.profile)
        return context
