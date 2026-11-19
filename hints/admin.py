from django.contrib import admin

from .models import HintRequest


@admin.register(HintRequest)
class HintRequestAdmin(admin.ModelAdmin):
    """Read-only history of hint requests (brief 5.5).

    Requests are made by participants on the task page; coaches decide them
    in the queue (#37), never in the admin.
    """

    list_display = ["nickname", "task", "hint_key", "status", "requested_at"]
    list_filter = ["status"]
    search_fields = [
        "task_attempt__user__profile__nickname",
        "task_attempt__user__profile__real_name",
        "task_attempt__task__versions__title",
    ]
    list_select_related = [
        "task_attempt__user__profile",
        "task_attempt__task_version",
        "hint",
    ]
    fields = [
        "task_attempt",
        "hint",
        "message",
        "status",
        "coach_reply",
        "decided_by",
        "requested_at",
        "decided_at",
    ]
    readonly_fields = fields

    @admin.display(
        description="Spitzname", ordering="task_attempt__user__profile__nickname"
    )
    def nickname(self, obj):
        user = obj.task_attempt.user
        profile = getattr(user, "profile", None)
        return profile.nickname if profile else user.get_username()

    @admin.display(description="Aufgabe")
    def task(self, obj):
        return obj.task_attempt.task_version.title

    @admin.display(description="Hinweis", ordering="hint__key")
    def hint_key(self, obj):
        return obj.hint.key

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
