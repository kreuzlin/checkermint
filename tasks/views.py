from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView, View

from accounts.roles import is_coach
from core.seo import SeoMixin
from submissions.progress import task_points
from submissions.services import get_draft, submitted_submissions
from submissions.switching import newer_version

from .attempts import TaskNotStartable, start_attempt, visible_version
from .catalogue import Status, catalogue, task_for


class CatalogueView(LoginRequiredMixin, SeoMixin, TemplateView):
    """All visible tasks by topic with their status (brief 5.9)."""

    template_name = "tasks/catalogue.html"
    page_title = "Aufgaben"
    meta_description = "Alle Aufgaben nach Thema, mit deinem Stand."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sections"] = catalogue(self.request.user)
        context["is_coach"] = is_coach(self.request.user)
        return context


class TaskDetailView(LoginRequiredMixin, SeoMixin, TemplateView):
    """The pinned or latest published version of a task (brief 5.4), and
    the participant's own submissions for it (brief 5.6).

    Locked tasks show only the title and the required level.
    """

    template_name = "tasks/task_detail.html"
    meta_description = "Anleitung und Anforderungen einer Aufgabe."

    def get(self, request, *args, **kwargs):
        user = request.user
        self.task, self.attempt, self.state = task_for(user, kwargs["slug"])
        self.version = visible_version(user, self.task)
        return super().get(request, *args, **kwargs)

    def get_page_title(self):
        return self.version.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        coach = is_coach(user)
        status = self.state.status
        participant = not coach and status is not Status.LOCKED
        context.update(
            task=self.task,
            version=self.version,
            attempt=self.attempt,
            state=self.state,
            is_locked=status is Status.LOCKED,
            can_start=participant and self.attempt is None,
            can_edit=participant and status is not Status.SUBMITTED,
            is_waiting=status is Status.SUBMITTED,
            is_coach=coach,
            draft=get_draft(user, self.task) if participant else None,
            newer=newer_version(self.attempt) if participant else None,
            submissions=submitted_submissions(user, self.task),
            earned=task_points(user, self.task) if participant else None,
            requirements=self.version.requirements.all(),
            hints=self.version.hints.all(),
        )
        return context


class StartTaskView(LoginRequiredMixin, View):
    """ "Aufgabe starten": pins the current version (brief 5.4)."""

    http_method_names = ["post"]

    def post(self, request, slug):
        task, attempt, state = task_for(request.user, slug)
        if attempt is not None:
            return redirect("tasks:task_detail", slug=task.slug)
        if state.is_locked or is_coach(request.user):
            messages.error(request, "Diese Aufgabe kannst du noch nicht starten.")
            return redirect("tasks:task_detail", slug=task.slug)
        try:
            start_attempt(request.user, task)
        except TaskNotStartable as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Los geht's! Die Aufgabe ist gestartet.")
        return redirect("tasks:task_detail", slug=task.slug)
