from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View

from accounts.mixins import CoachRequiredMixin
from accounts.roles import is_coach
from core.seo import SeoMixin
from tasks.attempts import visible_version
from tasks.catalogue import Status, catalogue, task_for

from .forms import (
    APPROVE,
    PhoneUploadForm,
    ReviewForm,
    SubmissionForm,
    stored_signature,
)
from .handlers import UploadHandler, handler_for
from .history import history_events
from .models import Submission
from .queue import queue_entries
from .services import (
    SubmissionNotAllowed,
    add_to_draft,
    ensure_draft,
    get_draft,
    items_by_requirement,
    review_submission,
    save_draft,
    starting_content,
    submit,
    submitted_submissions,
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


def participant_or_404(nickname):
    from accounts.views import participant_profiles

    return get_object_or_404(participant_profiles(), nickname__iexact=nickname).user


def has_uploads(version) -> bool:
    return any(
        isinstance(handler_for(r), UploadHandler) for r in version.requirements.all()
    )


class CoachUploadChooseView(CoachRequiredMixin, SeoMixin, TemplateView):
    """Coach: pick a task to add photos/files for a participant (#30)."""

    template_name = "submissions/coach_upload_choose.html"
    meta_description = "Fotos und Dateien für Teilnehmende hochladen."

    def get_page_title(self):
        return f"Hochladen für {self.participant.profile.nickname}"

    def get(self, request, *args, **kwargs):
        self.participant = participant_or_404(kwargs["nickname"])
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = []
        for section in catalogue(self.participant):
            for entry in section.entries:
                if has_uploads(entry.version):
                    entries.append(entry)
        context.update(participant=self.participant, entries=entries)
        return context


class CoachUploadView(CoachRequiredMixin, SeoMixin, TemplateView):
    """Coach adds photos/files to a participant's draft (brief 5.7, #30).

    Uses the same upload fields and image pipeline as the phone page; the
    participant submits the solution themselves.
    """

    template_name = "submissions/coach_upload.html"
    meta_description = "Fotos und Dateien für Teilnehmende hochladen."
    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not is_coach(request.user):
            return super().dispatch(request, *args, **kwargs)
        self.participant = participant_or_404(kwargs["nickname"])
        self.task, _, state = task_for(self.participant, kwargs["slug"])
        self.choose = redirect(
            "submissions:coach_upload_choose",
            nickname=self.participant.profile.nickname,
        )
        if state.is_locked:
            messages.error(request, "Diese Aufgabe ist für diese Person noch gesperrt.")
            return self.choose
        if state.status is Status.SUBMITTED:
            messages.info(request, "Die Lösung wartet schon auf einen Coach.")
            return self.choose
        self.version = visible_version(self.participant, self.task)
        self.draft = get_draft(self.participant, self.task)
        return super().dispatch(request, *args, **kwargs)

    def get_page_title(self):
        return f"Hochladen: {self.version.title}"

    def make_form(self, data=None, files=None):
        previous = (
            items_by_requirement(self.draft)
            if self.draft
            else starting_content(self.participant, self.task, self.version)
        )
        return PhoneUploadForm(
            self.version.requirements.all(), previous, data=data, files=files
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            participant=self.participant,
            task=self.task,
            version=self.version,
            draft=self.draft,
            form=kwargs.get("form") or self.make_form(),
        )
        return context

    def post(self, request, *args, **kwargs):
        try:
            self.draft = ensure_draft(self.participant, self.task)
        except SubmissionNotAllowed as error:
            messages.error(request, str(error))
            return self.choose
        form = self.make_form(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            add_to_draft(self.draft, form.items)
        except SubmissionNotAllowed as error:
            messages.error(request, str(error))
            return self.choose
        count = form.added_count()
        nickname = self.participant.profile.nickname
        messages.success(
            request,
            f"{count} {'Datei' if count == 1 else 'Dateien'} im Entwurf von "
            f"{nickname} gespeichert.",
        )
        return redirect(request.path)


class CoachQueueView(CoachRequiredMixin, SeoMixin, TemplateView):
    """Coach: everything waiting for a coach, oldest first (brief 5.10.1, #31)."""

    template_name = "submissions/queue.html"
    page_title = "Warteschlange"
    meta_description = "Eingereichte Lösungen, die auf einen Coach warten."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entries"] = queue_entries()
        return context


def next_in_queue(exclude_pk=None):
    """The oldest waiting entry other than `exclude_pk`, or None."""
    for entry in queue_entries():
        if entry.submission.pk != exclude_pk:
            return entry
    return None


class ReviewView(CoachRequiredMixin, SeoMixin, TemplateView):
    """Coach: review one submission (brief 5.8, #32).

    Stars and feedback, then "Annehmen" (1–3 stars) or "Überarbeitung
    nötig" (feedback only). With htmx only the form block is replaced;
    without JavaScript the page redirects to the queue.
    """

    template_name = "submissions/review.html"
    meta_description = "Eine eingereichte Lösung bewerten."
    http_method_names = ["get", "post"]

    def load_submission(self):
        # Only after CoachRequiredMixin.dispatch: participants get 403, never
        # a 404 that tells them which submission ids exist.
        self.submission = get_object_or_404(
            Submission.objects.exclude(status=Submission.Status.DRAFT).select_related(
                "user__profile", "task__topic", "task_version", "reviewed_by__profile"
            ),
            pk=self.kwargs["pk"],
        )

    def get(self, request, *args, **kwargs):
        self.load_submission()
        return super().get(request, *args, **kwargs)

    def get_page_title(self):
        return f"Bewerten: {self.submission.task_version.title}"

    @property
    def is_htmx(self) -> bool:
        return self.request.headers.get("HX-Request") == "true"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submission = self.submission
        latest = submission.task.latest_published_version()
        newer = (
            latest
            if latest and latest.number > submission.task_version.number
            else None
        )
        context.update(
            submission=submission,
            participant=submission.user,
            earlier=submitted_submissions(submission.user, submission.task).exclude(
                pk=submission.pk
            ),
            newer=newer,
            form=kwargs.get("form") or ReviewForm(),
            is_open=submission.status == Submission.Status.SUBMITTED,
            next_entry=next_in_queue(exclude_pk=submission.pk),
        )
        return context

    def post(self, request, *args, **kwargs):
        self.load_submission()
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return self.render_review(form=form)
        data = form.cleaned_data
        status = (
            Submission.Status.APPROVED
            if data["decision"] == APPROVE
            else Submission.Status.NEEDS_REVISION
        )
        try:
            self.submission = review_submission(
                self.submission, request.user, status, data["stars"], data["feedback"]
            )
        except SubmissionNotAllowed as error:
            self.load_submission()  # show the review that came first
            if self.is_htmx:
                return self.render_review(error=str(error))
            messages.error(request, str(error))
            return redirect("submissions:review", pk=self.submission.pk)
        nickname = self.submission.user.profile.nickname
        if status == Submission.Status.APPROVED:
            done = f"Lösung von {nickname} angenommen ({self.submission.star_symbols})."
        else:
            done = f"Lösung von {nickname} zur Überarbeitung zurückgegeben."
        if self.is_htmx:
            return self.render_review(done=done)
        messages.success(request, done)
        return redirect("submissions:queue")

    def render_review(self, **kwargs):
        context = self.get_context_data(**kwargs)
        if self.is_htmx:
            return render(self.request, "submissions/_review_form.html", context)
        return self.render_to_response(context)
