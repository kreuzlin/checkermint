from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import CoachRequiredMixin
from accounts.roles import is_coach
from notifications.emails import notify_coaches_of_hint_request
from tasks.attempts import TaskNotStartable
from tasks.catalogue import task_for

from .forms import GRANT, HintDecisionForm, HintRequestForm
from .models import HintRequest
from .services import HintRequestNotAllowed, decide_request, request_hint


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
            hint_request = request_hint(
                request.user, task, form.cleaned_data["message"]
            )
        except (HintRequestNotAllowed, TaskNotStartable) as error:
            messages.error(request, f"Fehler: {error}")
        else:
            notify_coaches_of_hint_request(request, hint_request)
            messages.success(
                request, "Deine Anfrage ist unterwegs. Ein Coach meldet sich."
            )
        return back


class DecideHintView(CoachRequiredMixin, View):
    """Coach: grant or decline a hint request in the queue (brief 5.10.1, #37).

    With htmx only the queue entry is replaced; without JavaScript the
    page redirects back to the queue with a message.
    """

    http_method_names = ["post"]

    def post(self, request, pk):
        # Only after CoachRequiredMixin.dispatch: participants get 403.
        self.hint_request = get_object_or_404(
            HintRequest.objects.select_related(
                "task_attempt__user__profile",
                "task_attempt__task__topic",
                "task_attempt__task_version",
                "hint__task_version",
                "decided_by__profile",
            ),
            pk=pk,
        )
        form = HintDecisionForm(request.POST)
        if not form.is_valid():
            error = next(iter(form.errors.values()))[0]
            return self.respond(error=error)
        status = (
            HintRequest.Status.GRANTED
            if form.cleaned_data["decision"] == GRANT
            else HintRequest.Status.DECLINED
        )
        try:
            self.hint_request = decide_request(
                self.hint_request, request.user, status, form.cleaned_data["reply"]
            )
        except HintRequestNotAllowed as error:
            self.hint_request.refresh_from_db()
            return self.respond(error=str(error))
        nickname = nickname_of(self.hint_request.task_attempt.user)
        verb = "freigegeben" if status == HintRequest.Status.GRANTED else "abgelehnt"
        return self.respond(done=f"Hinweis-Anfrage von {nickname} {verb}.")

    def respond(self, done=None, error=None):
        if self.request.headers.get("HX-Request") == "true":
            return render(
                self.request,
                "hints/_queue_entry.html",
                {"hint_request": self.hint_request, "done": done, "error": error},
            )
        if error:
            messages.error(self.request, f"Fehler: {error}")
        else:
            messages.success(self.request, done)
        return redirect("submissions:queue")


def nickname_of(user):
    profile = getattr(user, "profile", None)
    return profile.nickname if profile else user.get_username()
