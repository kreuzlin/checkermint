from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View

from accounts.roles import is_coach
from tasks.attempts import TaskNotStartable
from tasks.catalogue import task_for

from .forms import HintRequestForm
from .services import HintRequestNotAllowed, request_hint


class RequestHintView(LoginRequiredMixin, View):
    """ "Hinweis anfragen" on the task page (brief 5.5, #36)."""

    http_method_names = ["post"]

    def post(self, request, slug):
        task, _attempt, state = task_for(request.user, slug)
        back = redirect("tasks:task_detail", slug=task.slug)
        if state.is_locked or is_coach(request.user):
            messages.error(
                request, "Für diese Aufgabe kannst du keinen Hinweis anfragen."
            )
            return back
        form = HintRequestForm(request.POST)
        if not form.is_valid():
            messages.error(
                request, "Fehler: Die Nachricht ist zu lang (höchstens 300 Zeichen)."
            )
            return back
        try:
            request_hint(request.user, task, form.cleaned_data["message"])
        except (HintRequestNotAllowed, TaskNotStartable) as error:
            messages.error(request, f"Fehler: {error}")
        else:
            messages.success(
                request, "Deine Anfrage ist unterwegs. Ein Coach meldet sich."
            )
        return back
