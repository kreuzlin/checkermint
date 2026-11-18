from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Badge, available_images


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
