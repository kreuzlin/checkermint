from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from core.images import process_image
from core.private_files import private_file_url

from .models import (
    Hint,
    InstructionImage,
    LevelThreshold,
    Task,
    TaskRequirement,
    TaskVersion,
    Topic,
)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name", "order", "slug"]
    list_editable = ["order"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ["name"]}
    fields = ["name", "slug", "order", "description"]


@admin.register(LevelThreshold)
class LevelThresholdAdmin(admin.ModelAdmin):
    """Shared level table (ADR 0013). Changes apply to everyone at once."""

    list_display = ["level", "min_points"]
    list_display_links = ["level"]
    actions = None  # no bulk delete: it could leave gaps

    def get_readonly_fields(self, request, obj=None):
        # The level number is fixed once created; only the points change.
        return ["level"] if obj else []

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not obj.can_be_deleted():
            return False
        return super().has_delete_permission(request, obj)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "Level-Schwellen (gelten für alle Themen)"
        return super().changelist_view(request, extra_context)


# --- Tasks and versions (brief 5.4, ADR 0010) -----------------------------


class VersionListInline(admin.TabularInline):
    """All versions of a task, read-only; each links to its own page."""

    model = TaskVersion
    verbose_name = "Version"
    verbose_name_plural = "Versionen"
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ["number", "status", "title", "published_at", "change_note", "pinned"]
    readonly_fields = fields
    ordering = ["-number"]

    @admin.display(description="Teilnehmende auf dieser Version")
    def pinned(self, obj):
        return obj.attempts.count()

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class InstructionImageForm(forms.ModelForm):
    class Meta:
        model = InstructionImage
        fields = ["image", "alt_text"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Uploaded images are immutable: upload a new one instead.
            for field in self.fields.values():
                field.disabled = True

    def clean_image(self):
        uploaded = self.cleaned_data.get("image")
        if self.instance.pk or not uploaded:
            return uploaded
        processed = process_image(uploaded)
        self.original_filename = uploaded.name[:200]
        processed.content.name = f"bild{processed.extension}"
        return processed.content

    def save(self, commit=True):
        if hasattr(self, "original_filename"):
            self.instance.original_filename = self.original_filename
        return super().save(commit=commit)


class InstructionImageFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            image = form.instance
            if (
                self.can_delete
                and self._should_delete_form(form)
                and image.pk
                and image.used_by_published_version()
            ):
                raise forms.ValidationError(
                    f"«{image.alt_text}» wird von einer veröffentlichten Version "
                    "verwendet und kann nicht gelöscht werden."
                )


class InstructionImageInline(admin.TabularInline):
    """Upload images, then paste their Markdown into a draft version."""

    model = InstructionImage
    form = InstructionImageForm
    formset = InstructionImageFormSet
    extra = 1
    fields = ["preview", "image", "alt_text", "reference", "used_in"]
    readonly_fields = ["preview", "reference", "used_in"]
    verbose_name_plural = (
        "Bilder in der Anleitung (hochladen, dann den Markdown-Code in die "
        "Anleitung des Entwurfs kopieren)"
    )

    @admin.display(description="Vorschau")
    def preview(self, obj):
        if not obj.pk:
            return ""
        return format_html(
            '<img src="{}" alt="" style="max-width: 120px; max-height: 80px">',
            private_file_url("anleitungsbild", obj),
        )

    @admin.display(description="In die Anleitung kopieren")
    def reference(self, obj):
        if not obj.pk:
            return "Nach dem Speichern"
        return format_html("<code>{}</code>", obj.reference)

    @admin.display(description="Verwendet in")
    def used_in(self, obj):
        if not obj.pk:
            return ""
        versions = obj.versions_using()
        return ", ".join(f"Version {v.number}" for v in versions) or "–"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "topic",
        "order",
        "min_level",
        "current_version",
        "has_draft",
        "is_published",
        "is_archived",
    ]
    list_filter = ["topic", "is_published", "is_archived"]
    search_fields = ["slug", "versions__title"]
    list_select_related = ["topic"]
    fields = [
        "topic",
        "slug",
        "order",
        "min_level",
        "badge",
        "is_published",
        "is_archived",
    ]
    inlines = [InstructionImageInline, VersionListInline]

    def get_queryset(self, request):
        return super().get_queryset(request).distinct()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if isinstance(instance, InstructionImage) and instance.pk is None:
                instance.uploaded_by = request.user
            instance.save()
        formset.save_m2m()

    @admin.display(description="Aktuelle Version")
    def current_version(self, obj):
        version = obj.latest_published_version()
        return version.number if version else "–"

    @admin.display(description="Entwurf", boolean=True)
    def has_draft(self, obj):
        return obj.versions.drafts().exists()

    def get_urls(self):
        urls = [
            path(
                "<int:task_id>/neue-version/",
                self.admin_site.admin_view(self.new_version_view),
                name="tasks_task_new_version",
            ),
        ]
        return urls + super().get_urls()

    def new_version_view(self, request, task_id):
        """POST: copy the latest version into a draft, then open the draft."""
        task = get_object_or_404(Task, pk=task_id)
        if request.method != "POST" or not request.user.has_perm(
            "tasks.add_taskversion"
        ):
            raise PermissionDenied
        had_draft = task.draft_version() is not None
        draft = task.create_draft(user=request.user)
        if had_draft:
            messages.info(request, "Es gibt schon einen Entwurf; hier ist er.")
        else:
            messages.success(
                request,
                f"Entwurf Version {draft.number} erstellt. Bearbeite ihn und "
                "veröffentliche ihn, wenn er fertig ist.",
            )
        return redirect("admin:tasks_taskversion_change", draft.pk)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        task = self.get_object(request, object_id)
        if task is not None:
            extra_context["draft"] = task.draft_version()
            extra_context["can_add_version"] = request.user.has_perm(
                "tasks.add_taskversion"
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        messages.info(
            request,
            "Als Nächstes: «Neue Version erstellen» und Titel, Anleitung, "
            "Anforderungen und Hinweise eintragen.",
        )
        return redirect("admin:tasks_task_change", obj.pk)


class VersionChildInline(admin.StackedInline):
    """Requirements and hints: editable in drafts, read-only once published."""

    extra = 0

    def _editable(self, obj):
        return obj is not None and not obj.stored_is_published()

    def has_add_permission(self, request, obj=None):
        return self._editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._editable(obj) and super().has_delete_permission(request, obj)


class RequirementInline(VersionChildInline):
    model = TaskRequirement
    fields = [
        ("label", "key"),
        ("type", "required", "min_count", "max_count", "order"),
        "help_text",
        "options",
    ]
    prepopulated_fields = {"key": ["label"]}


class HintInline(VersionChildInline):
    model = Hint
    fields = [("key", "order"), "text"]


@admin.register(TaskVersion)
class TaskVersionAdmin(admin.ModelAdmin):
    """Versions are opened from their task; published ones are read-only."""

    list_display = ["__str__", "task", "number", "status", "published_at"]
    list_filter = ["status"]
    actions = None  # no bulk delete
    inlines = [RequirementInline, HintInline]
    readonly_fields = [
        "task_link",
        "number",
        "status",
        "created_by",
        "created_at",
        "published_at",
    ]
    fieldsets = [
        (None, {"fields": ["task_link", "number", "status"]}),
        (
            "Inhalt",
            {"fields": ["title", "instructions", "base_points", "change_note"]},
        ),
        ("Verlauf", {"fields": ["created_by", "created_at", "published_at"]}),
    ]

    def get_model_perms(self, request):
        # Not listed on the admin index: versions are reached via their task.
        return {}

    def has_add_permission(self, request):
        # New versions come from "Neue Version erstellen" on the task.
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.stored_is_published():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.stored_is_published():
            return False
        return super().has_delete_permission(request, obj)

    @admin.display(description="Aufgabe")
    def task_link(self, obj):
        url = reverse("admin:tasks_task_change", args=[obj.task_id])
        return format_html('<a href="{}">{}</a>', url, obj.task.slug)

    def get_urls(self):
        urls = [
            path(
                "<int:version_id>/veroeffentlichen/",
                self.admin_site.admin_view(self.publish_view),
                name="tasks_taskversion_publish",
            ),
            path(
                "<int:version_id>/vorschau/",
                self.admin_site.admin_view(self.preview_view),
                name="tasks_taskversion_preview",
            ),
        ]
        return urls + super().get_urls()

    def publish_view(self, request, version_id):
        version = get_object_or_404(TaskVersion, pk=version_id)
        if not self.has_change_permission(request, version):
            raise PermissionDenied
        if request.method == "POST":
            try:
                version.publish()
            except ValidationError as error:
                for message in error.messages:
                    messages.error(request, message)
                return redirect("admin:tasks_taskversion_change", version.pk)
            text = f"Version {version.number} ist veröffentlicht."
            if not version.task.is_published:
                text += (
                    " Die Aufgabe ist noch nicht für Teilnehmende sichtbar: "
                    "Häkchen «Für Teilnehmende sichtbar» setzen."
                )
            messages.success(request, text)
            return redirect("admin:tasks_task_change", version.task_id)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": f"Version {version.number} veröffentlichen?",
            "version": version,
            "previous": version.task.latest_published_version(),
        }
        return TemplateResponse(
            request, "admin/tasks/taskversion/publish_confirm.html", context
        )

    def preview_view(self, request, version_id):
        """The version as participants will see it (site layout)."""
        version = get_object_or_404(TaskVersion, pk=version_id)
        if not self.has_view_permission(request, version):
            raise PermissionDenied
        context = {
            "version": version,
            "task": version.task,
            "requirements": version.requirements.all(),
            "hints": version.hints.all(),
            "page_title": f"Vorschau: {version.title}",
        }
        return TemplateResponse(request, "tasks/version_preview.html", context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        version = self.get_object(request, object_id)
        if version is not None:
            extra_context["can_publish"] = self.has_change_permission(request, version)
        return super().change_view(request, object_id, form_url, extra_context)

    def response_delete(self, request, obj_display, obj_id):
        messages.success(request, f"Entwurf «{obj_display}» gelöscht.")
        return redirect("admin:tasks_task_changelist")
