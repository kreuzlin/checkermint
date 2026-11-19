from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("<slug:slug>/loesung/", views.SubmissionView.as_view(), name="edit"),
    path("<slug:slug>/wechseln/", views.SwitchVersionView.as_view(), name="switch"),
]
