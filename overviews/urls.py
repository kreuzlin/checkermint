from django.urls import path

from . import views

app_name = "overviews"

urlpatterns = [
    path("fortschritt/", views.ProgressMatrixView.as_view(), name="matrix"),
    path(
        "fortschritt/teilnehmende/<str:nickname>/",
        views.ParticipantDetailView.as_view(),
        name="participant",
    ),
]
