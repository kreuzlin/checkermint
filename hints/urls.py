from django.urls import path

from . import views

app_name = "hints"

urlpatterns = [
    path(
        "<slug:slug>/hinweis-anfragen/",
        views.RequestHintView.as_view(),
        name="request",
    ),
]
