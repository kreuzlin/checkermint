from django import forms
from django.contrib import admin
from django.utils.html import format_html

from accounts.roles import is_coach

from .images import process_badge_image
from .models import Badge, UserBadge

# Required by the maintainer (ADR 0018): badge images are public.
UPLOAD_NOTICE = (
    "Keine Fotos von Personen hochladen – nur Grafiken. Das Bild ist "
    "öffentlich sichtbar (öffentliche Profile). Erlaubt: PNG oder WebP, "
    "höchstens 2 MB. Das Bild wird neu gespeichert, auf das Motiv "
    "zugeschnitten und auf 512 × 512 Pixel zentriert."
)


class BadgeForm(forms.ModelForm):
    upload = forms.FileField(
        label="Bild hochladen",
        required=False,
        help_text=UPLOAD_NOTICE,
        widget=forms.ClearableFileInput(attrs={"accept": "image/png,image/webp"}),
    )
    remove_image = forms.BooleanField(
        label="Bild entfernen (Platzhalter zeigen)", required=False
    )

    class Meta:
        model = Badge
        fields = ["name", "description"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only coaches and superusers upload (ADR 0018); the admin is staff
        # only, but a staff user outside the coach group must not.
        if user is None or not is_coach(user):
            for name in ("upload", "remove_image"):
                self.fields[name].disabled = True
                self.fields[name].help_text = "Nur Coaches können Bilder ändern."
        self._processed = None

    def clean_upload(self):
        upload = self.cleaned_data.get("upload")
        if upload:
            self._processed = process_badge_image(upload)
        return upload

    def save(self, commit=True):
        badge = super().save(commit=False)
        if self._processed is not None:
            badge.set_image(self._processed)
        elif self.cleaned_data.get("remove_image") and badge.image_file:
            badge.remove_image()
        if commit:
            badge.save()
        return badge


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    form = BadgeForm
    list_display = ["preview", "name", "description"]
    list_display_links = ["preview", "name"]
    search_fields = ["name", "description"]
    readonly_fields = ["preview", "created_at"]
    fields = ["name", "description", "preview", "upload", "remove_image", "created_at"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        class FormForUser(form):
            def __init__(self, *args, **kw):
                super().__init__(*args, user=request.user, **kw)

        return FormForUser

    @admin.display(description="Bild")
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
