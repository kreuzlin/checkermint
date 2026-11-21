"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from tasks.simulator import simulator_file

admin.site.site_header = f"{settings.SITE_SHORT_NAME} – Verwaltung"
admin.site.site_title = f"{settings.SITE_SHORT_NAME} Verwaltung"
admin.site.index_title = "Inhalte verwalten"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Feature apps go here, e.g. path("kontakt/", include("contact.urls")).
    path("aufgaben/", include("tasks.urls")),
    # GearsBot world, robot and filter JSON of task versions (ADR 0021).
    path("sim/<slug:token>/<str:filename>", simulator_file, name="simulator_file"),
    path("", include("badges.urls")),
    path("", include("hints.urls")),
    path("", include("overviews.urls")),
    path("", include("submissions.urls")),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
]
# Uploaded files are never served from a public URL, not even in development
# (ADR 0009); a view with access checks serves them.
