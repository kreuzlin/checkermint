from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("<slug:slug>/loesung/", views.SubmissionView.as_view(), name="edit"),
]
