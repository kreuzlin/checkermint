from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("aufgaben/<slug:slug>/loesung/", views.SubmissionView.as_view(), name="edit"),
    path(
        "aufgaben/<slug:slug>/loesung/gespeichert/<slug:key>/",
        views.StoredItemsView.as_view(),
        name="stored",
    ),
    path(
        "aufgaben/<slug:slug>/wechseln/",
        views.SwitchVersionView.as_view(),
        name="switch",
    ),
    path("verlauf/", views.HistoryView.as_view(), name="history"),
    path(
        "hochladen/<str:token>/",
        views.PhoneUploadView.as_view(),
        name="phone_upload",
    ),
]
