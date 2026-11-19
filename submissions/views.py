from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from accounts.roles import is_coach
from core.seo import SeoMixin
from tasks.attempts import visible_version
from tasks.catalogue import Status, task_for

from .forms import SubmissionForm
from .services import (
    SubmissionNotAllowed,
    get_draft,
    save_draft,
    starting_content,
    submit,
)
from .switching import SwitchNotPossible, newer_version, plan_switch, switch_version

SAVE, SUBMIT = "speichern", "einreichen"


class SubmissionView(LoginRequiredMixin, SeoMixin, TemplateView):
    """Fill in, save and submit a solution (brief 5.6).

    "Entwurf speichern" keeps the draft without checks for completeness;
    "Einreichen" saves and submits if all required parts are there.
    """

    template_name = "submissions/form.html"
    meta_description = "Lösung für eine Aufgabe erfassen und einreichen."
    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        user = request.user
        self.task, self.attempt, state = task_for(user, kwargs["slug"])
        detail = redirect("tasks:task_detail", slug=self.task.slug)
        if is_coach(user) or state.is_locked:
            messages.error(
                request, "Für diese Aufgabe kannst du keine Lösung einreichen."
            )
            return detail
        if state.status is Status.SUBMITTED:
            messages.info(request, "Deine Lösung wartet auf einen Coach.")
            return detail
        self.version = visible_version(user, self.task)
        self.previous = starting_content(user, self.task, self.version)
        return super().dispatch(request, *args, **kwargs)

    def get_page_title(self):
        return f"Lösung: {self.version.title}"

    def make_form(self, data=None, files=None):
        return SubmissionForm(
            self.version.requirements.all(), self.previous, data=data, files=files
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get("form") or self.make_form()
        context.update(
            task=self.task,
            version=self.version,
            form=form,
            draft=get_draft(self.request.user, self.task),
            newer=newer_version(self.attempt),
            unsupported_required=form.unsupported_required(),
        )
        return context

    def post(self, request, *args, **kwargs):
        form = self.make_form(request.POST, request.FILES)
        action = request.POST.get("aktion")
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            draft = save_draft(request.user, self.task, form.items)
        except SubmissionNotAllowed as error:
            messages.error(request, str(error))
            return redirect("tasks:task_detail", slug=self.task.slug)
        if action != SUBMIT:
            messages.success(request, "Dein Entwurf ist gespeichert.")
            return redirect("submissions:edit", slug=self.task.slug)
        if not form.check_complete():
            messages.error(
                request,
                "Dein Entwurf ist gespeichert, aber es fehlt noch etwas. "
                "Schau dir die markierten Felder an.",
            )
            return self.render_to_response(self.get_context_data(form=form))
        try:
            submit(draft)
        except SubmissionNotAllowed as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request, "Super, deine Lösung ist eingereicht! Ein Coach schaut sie an."
            )
        return redirect("tasks:task_detail", slug=self.task.slug)


class SwitchVersionView(LoginRequiredMixin, SeoMixin, TemplateView):
    """ "Auf neue Version wechseln" with a confirmation (brief 5.4)."""

    template_name = "submissions/switch_confirm.html"
    meta_description = "Auf die neuste Version einer Aufgabe wechseln."
    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.task, _, state = task_for(request.user, kwargs["slug"])
        self.detail = redirect("tasks:task_detail", slug=self.task.slug)
        if is_coach(request.user) or state.is_locked:
            return self.detail
        try:
            self.plan = plan_switch(request.user, self.task)
        except SwitchNotPossible as error:
            messages.info(request, str(error))
            return self.detail
        return super().dispatch(request, *args, **kwargs)

    def get_page_title(self):
        return f"Neue Version: {self.plan.target.title}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(task=self.task, plan=self.plan)
        return context

    def post(self, request, *args, **kwargs):
        try:
            target_id = int(request.POST.get("version", ""))
            switch_version(request.user, self.task, target_id)
        except ValueError:
            return self.detail
        except SwitchNotPossible as error:
            messages.error(request, str(error))
            return redirect("submissions:switch", slug=self.task.slug)
        messages.success(
            request, f"Du arbeitest jetzt mit Version {self.plan.target.number}."
        )
        return self.detail
