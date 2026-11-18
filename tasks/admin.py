from django.contrib import admin

from .models import LevelThreshold, Topic


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
