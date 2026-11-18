"""Admin for accounts and profiles.

Coaches (staff in the group "Coach", never superusers) manage participant
accounts: create them with a profile in one form, edit them, set a new
password, deactivate them. They never see or change staff or superuser
accounts, and they can never grant staff, superuser, group or permission
rights (brief, sections 2 and 5.1).
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import Profile

User = get_user_model()

VISIBILITY_DESCRIPTION = (
    "Spitzname, Avatar, Punkte und Level sind immer öffentlich. "
    "Echter Name und E-Mail-Adresse nie."
)


def is_admin(request) -> bool:
    return request.user.is_superuser


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    max_num = 1
    verbose_name_plural = "Profil"
    readonly_fields = ["avatar_seed"]
    fieldsets = [
        (None, {"fields": ["nickname", "real_name", "about"]}),
        (
            "Sichtbarkeit im öffentlichen Profil",
            {
                "description": VISIBILITY_DESCRIPTION,
                "fields": ["show_badges", "show_about", "show_solved_tasks"],
            },
        ),
        ("Benachrichtigungen", {"fields": ["email_notifications"]}),
    ]

    def get_min_num(self, request, obj=None, **kwargs):
        # Every participant account needs a profile; admins may create
        # accounts without one (e.g. for coaches).
        return 0 if is_admin(request) else 1

    def get_formset(self, request, obj=None, **kwargs):
        # Enforce min_num on the server too, not only in the rendered form.
        kwargs.setdefault("validate_min", not is_admin(request))
        return super().get_formset(request, obj, **kwargs)


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [ProfileInline]
    list_display = [
        "username",
        "nickname",
        "real_name",
        "email",
        "is_active",
        "is_staff",
        "last_login",
    ]
    search_fields = [
        "username",
        "email",
        "profile__nickname",
        "profile__real_name",
    ]
    list_select_related = ["profile"]

    # Fieldsets for coaches (participant accounts only).
    coach_add_fieldsets = [
        (
            None,
            {
                "fields": ["username", "password1", "password2", "email"],
                "description": (
                    "Benutzername und Passwort gibst du der Teilnehmerin oder "
                    "dem Teilnehmer persönlich weiter. Die E-Mail-Adresse ist "
                    "freiwillig (nur für das Zurücksetzen des Passworts und "
                    "Benachrichtigungen)."
                ),
            },
        ),
    ]
    coach_change_fieldsets = [
        (None, {"fields": ["username", "password"]}),
        ("Kontakt", {"fields": ["email"]}),
        (
            "Status",
            {
                "fields": ["is_active"],
                "description": (
                    "Konten werden nicht gelöscht, sondern deaktiviert: "
                    "Häkchen bei «Aktiv» entfernen."
                ),
            },
        ),
        ("Daten", {"fields": ["last_login", "date_joined"]}),
    ]

    @admin.display(description="Spitzname", ordering="profile__nickname")
    def nickname(self, obj):
        return getattr(getattr(obj, "profile", None), "nickname", "–")

    @admin.display(description="Echter Name", ordering="profile__real_name")
    def real_name(self, obj):
        return getattr(getattr(obj, "profile", None), "real_name", "–")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_admin(request):
            return qs
        return qs.filter(is_staff=False, is_superuser=False)

    def get_list_display(self, request):
        fields = super().get_list_display(request)
        if is_admin(request):
            return fields
        return [f for f in fields if f != "is_staff"]

    def get_list_filter(self, request):
        if is_admin(request):
            return super().get_list_filter(request)
        return ["is_active"]

    def get_fieldsets(self, request, obj=None):
        if is_admin(request):
            return super().get_fieldsets(request, obj)
        return self.coach_add_fieldsets if obj is None else self.coach_change_fieldsets

    def get_readonly_fields(self, request, obj=None):
        if is_admin(request):
            return super().get_readonly_fields(request, obj)
        return ["last_login", "date_joined"]

    def get_form(self, request, obj=None, **kwargs):
        if obj is None and not is_admin(request):
            # No "unusable password" option: participants always log in with
            # a password.
            kwargs["form"] = UserCreationForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not is_admin(request):
            # Defence in depth: the coach forms do not contain these fields.
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Overview of profiles; profiles are created together with the account."""

    list_display = ["nickname", "real_name", "user", "email_notifications"]
    search_fields = ["nickname", "real_name", "user__username"]
    list_filter = ["show_badges", "show_about", "show_solved_tasks"]
    readonly_fields = ["user", "avatar_seed", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["user", "nickname", "real_name", "about"]}),
        (
            "Sichtbarkeit im öffentlichen Profil",
            {
                "description": VISIBILITY_DESCRIPTION,
                "fields": ["show_badges", "show_about", "show_solved_tasks"],
            },
        ),
        ("Benachrichtigungen", {"fields": ["email_notifications"]}),
        ("Technisch", {"fields": ["avatar_seed", "created_at", "updated_at"]}),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("user")
        if is_admin(request):
            return qs
        return qs.filter(user__is_staff=False, user__is_superuser=False)

    def has_add_permission(self, request):
        return False
