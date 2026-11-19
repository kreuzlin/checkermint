from django.contrib import admin

from .models import Submission, SubmissionItem


class SubmissionItemInline(admin.TabularInline):
    model = SubmissionItem
    fields = ["requirement", "order", "text", "original_filename"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Read-only overview for coaches; submitting and reviewing happen in
    the participant and coach views (#23, #31, #32)."""

    list_display = [
        "user",
        "task_title",
        "version_number",
        "status",
        "stars",
        "submitted_at",
    ]
    list_filter = ["status", "task__topic"]
    search_fields = ["user__username", "user__profile__nickname"]
    date_hierarchy = "submitted_at"
    list_select_related = ["user", "task_version"]
    fields = [
        "user",
        "task",
        "task_version",
        "status",
        "stars",
        "feedback",
        "reviewed_by",
        "created_at",
        "submitted_at",
        "reviewed_at",
    ]
    readonly_fields = fields
    inlines = [SubmissionItemInline]
    actions = None

    @admin.display(description="Aufgabe", ordering="task__slug")
    def task_title(self, obj):
        return obj.task_version.title

    @admin.display(description="Version", ordering="task_version__number")
    def version_number(self, obj):
        return obj.task_version.number

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
