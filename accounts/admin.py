from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["nickname", "real_name", "user", "email_notifications"]
    search_fields = ["nickname", "real_name", "user__username"]
    list_filter = ["show_badges", "show_about", "show_solved_tasks"]
    readonly_fields = ["avatar_seed", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["user", "nickname", "real_name", "about"]}),
        (
            "Sichtbarkeit im öffentlichen Profil",
            {
                "description": (
                    "Spitzname, Avatar, Punkte und Level sind immer öffentlich. "
                    "Echter Name und E-Mail-Adresse nie."
                ),
                "fields": ["show_badges", "show_about", "show_solved_tasks"],
            },
        ),
        ("Benachrichtigungen", {"fields": ["email_notifications"]}),
        ("Technisch", {"fields": ["avatar_seed", "created_at", "updated_at"]}),
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        # The account of an existing profile is fixed.
        if obj is not None:
            fields.append("user")
        return fields
