from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, View

from accounts.roles import is_coach
from core.seo import SeoMixin

from .attempts import TaskNotStartable, get_attempt, start_attempt, visible_version
from .catalogue import Status, catalogue, levels_by_topic, task_status, visible_tasks


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


def task_for(user, slug):
    """A visible task and its status for `user` (404 if not visible)."""
    task = get_object_or_404(visible_tasks().select_related("topic"), slug=slug)
    attempt = get_attempt(user, task)
    level = levels_by_topic(user, [task.topic_id])[task.topic_id]
    status = task_status(user, task, level, started=attempt is not None)
    return task, attempt, status


class TaskDetailView(LoginRequiredMixin, SeoMixin, TemplateView):
    """The pinned or latest published version of a task (brief 5.4).

    Locked tasks show only the title and the required level.
    """

    template_name = "tasks/task_detail.html"
    meta_description = "Anleitung und Anforderungen einer Aufgabe."

    def get(self, request, *args, **kwargs):
        user = request.user
        self.task, self.attempt, self.status = task_for(user, kwargs["slug"])
        self.version = visible_version(user, self.task)
        return super().get(request, *args, **kwargs)

    def get_page_title(self):
        return self.version.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        coach = is_coach(self.request.user)
        context.update(
            task=self.task,
            version=self.version,
            attempt=self.attempt,
            status=self.status,
            is_locked=self.status is Status.LOCKED,
            can_start=self.attempt is None and self.status is Status.OPEN and not coach,
            is_coach=coach,
            requirements=self.version.requirements.all(),
            hints=self.version.hints.all(),
        )
        return context


class StartTaskView(LoginRequiredMixin, View):
    """ "Aufgabe starten": pins the current version (brief 5.4)."""

    http_method_names = ["post"]

    def post(self, request, slug):
        task, attempt, status = task_for(request.user, slug)
        if attempt is not None:
            return redirect("tasks:task_detail", slug=task.slug)
        if status is Status.LOCKED or is_coach(request.user):
            messages.error(request, "Diese Aufgabe kannst du noch nicht starten.")
            return redirect("tasks:task_detail", slug=task.slug)
        try:
            start_attempt(request.user, task)
        except TaskNotStartable as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Los geht's! Die Aufgabe ist gestartet.")
        return redirect("tasks:task_detail", slug=task.slug)
