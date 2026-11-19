from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("datenschutz/", views.PrivacyView.as_view(), name="privacy"),
    path("impressum/", views.ImprintView.as_view(), name="imprint"),
    path("version", views.version, name="version"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    # Private uploads (ADR 0009), e.g. /dateien/anleitungsbild/12/
    path("dateien/<slug:kind>/<int:pk>/", views.private_file, name="private_file"),
    path(
        "dateien/<slug:kind>/<int:pk>/<slug:variant>/",
        views.private_file,
        name="private_file",
    ),
]
