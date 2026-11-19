from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView, View

from accounts.roles import is_coach
from core.seo import SeoMixin
from tasks.attempts import visible_version
from tasks.catalogue import Status, task_for

from .forms import PhoneUploadForm, SubmissionForm, stored_signature
from .handlers import UploadHandler, handler_for
from .history import history_events
from .services import (
    SubmissionNotAllowed,
    add_to_draft,
    get_draft,
    items_by_requirement,
    save_draft,
    starting_content,
    submit,
)
from .switching import SwitchNotPossible, newer_version, plan_switch, switch_version
from .upload_links import (
    LIFETIME_MINUTES,
    InvalidUploadLink,
    draft_for_token,
    qr_svg,
    upload_url,
)

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
            phone_upload=self.phone_upload(form),
            unsupported_required=form.unsupported_required(),
        )
        return context

    def phone_upload(self, form):
        """QR code for the phone, if there is a draft with photos or files."""
        draft = get_draft(self.request.user, self.task)
        has_uploads = any(isinstance(row.handler, UploadHandler) for row in form.rows)
        if not has_uploads:
            return None
        if draft is None:
            return {"needs_draft": True}
        url = upload_url(self.request, draft)
        return {"url": url, "qr": qr_svg(url), "minutes": LIFETIME_MINUTES}

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


class HistoryView(LoginRequiredMixin, SeoMixin, TemplateView):
    """Everything the participant has submitted and achieved (brief 5.9)."""

    template_name = "submissions/history.html"
    page_title = "Mein Verlauf"
    meta_description = "Alle deine Einreichungen und Bewertungen."
    paginate_by = 30

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = Paginator(history_events(self.request.user), self.paginate_by)
        context["page_obj"] = paginator.get_page(self.request.GET.get("seite"))
        return context


class PhoneUploadView(SeoMixin, TemplateView):
    """Upload page behind the QR code: no login, the signed link is the key
    (brief 5.7). Shows only the task title and the requirement labels."""

    template_name = "submissions/phone_upload.html"
    page_title = "Fotos hochladen"
    meta_description = "Fotos und Dateien zu einer Lösung hochladen."
    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        try:
            self.draft = draft_for_token(kwargs["token"])
        except InvalidUploadLink as error:
            return render(
                request,
                "submissions/phone_upload_invalid.html",
                {"page_title": "Link ungültig", "message": error.message},
                status=410,
            )
        return super().dispatch(request, *args, **kwargs)

    def make_form(self, data=None, files=None):
        return PhoneUploadForm(
            self.draft.task_version.requirements.all(),
            items_by_requirement(self.draft),
            data=data,
            files=files,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(draft=self.draft, form=kwargs.get("form") or self.make_form())
        return context

    def post(self, request, *args, **kwargs):
        form = self.make_form(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            add_to_draft(self.draft, form.items)
        except SubmissionNotAllowed as error:
            messages.error(request, str(error))
        else:
            count = form.added_count()
            messages.success(
                request,
                "1 Datei ist hochgeladen."
                if count == 1
                else f"{count} Dateien sind hochgeladen.",
            )
        return redirect(request.path)


STOP_POLLING = 286  # htmx stops polling on this status


class StoredItemsView(LoginRequiredMixin, View):
    """htmx: the stored photos/files of one requirement of the draft, or 204
    if nothing changed since `stand` (brief 5.7, #29)."""

    http_method_names = ["get"]

    def get(self, request, slug, key):
        user = request.user
        task, _, state = task_for(user, slug)
        draft = get_draft(user, task)
        if is_coach(user) or state.is_locked or draft is None:
            return HttpResponse(status=STOP_POLLING)
        requirement = draft.task_version.requirements.filter(key=key).first()
        if requirement is None or not isinstance(
            handler_for(requirement), UploadHandler
        ):
            return HttpResponse(status=STOP_POLLING)
        items = items_by_requirement(draft).get(requirement.pk, [])
        signature = stored_signature(items)
        if request.GET.get("stand") == signature:
            return HttpResponse(status=204)
        return render(
            request,
            "submissions/fields/_stored.html",
            {
                "task": task,
                "requirement": requirement,
                "items": items,
                "checked": request.GET.getlist(f"{key}-entfernen"),
                "signature": signature,
                "live": True,
            },
        )
