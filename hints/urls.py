from django.urls import path

from . import views

app_name = "hints"

urlpatterns = [
    path(
        "aufgaben/<slug:slug>/hinweis-anfragen/",
        views.RequestHintView.as_view(),
        name="request",
    ),
    path(
        "warteschlange/hinweis/<int:pk>/",
        views.DecideHintView.as_view(),
        name="decide",
    ),
]
