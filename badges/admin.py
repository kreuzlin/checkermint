from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Badge, UserBadge, available_images


class BadgeForm(forms.ModelForm):
    class Meta:
        model = Badge
        fields = ["name", "description", "image"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "– Platzhalter –")] + [(n, n) for n in available_images()]
        current = self.instance.image
        if current and current not in available_images():
            choices.append((current, f"{current} (fehlt)"))
        self.fields["image"].widget = forms.Select(choices=choices)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    form = BadgeForm
    list_display = ["preview", "name", "description"]
    list_display_links = ["preview", "name"]
    search_fields = ["name", "description"]
    readonly_fields = ["preview", "created_at"]
    fields = ["name", "description", "image", "preview", "created_at"]

    @admin.display(description="Vorschau")
    def preview(self, obj):
        if obj and obj.image_url:
            return format_html(
                '<img src="{}" alt="" width="48" height="48">', obj.image_url
            )
        return "Platzhalter"


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    """Awards come from reviews; coaches can only look and revoke (delete)."""

    list_display = ["badge", "nickname", "task", "awarded_at"]
    list_filter = ["badge"]
    search_fields = ["user__profile__nickname", "user__profile__real_name"]
    list_select_related = ["badge", "user__profile", "submission__task_version"]
    fields = ["badge", "user", "submission", "awarded_at"]
    readonly_fields = fields

    @admin.display(description="Spitzname", ordering="user__profile__nickname")
    def nickname(self, obj):
        profile = getattr(obj.user, "profile", None)
        return profile.nickname if profile else obj.user.get_username()

    @admin.display(description="Aufgabe")
    def task(self, obj):
        return obj.submission.task_version.title if obj.submission else "–"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
