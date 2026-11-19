from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.CatalogueView.as_view(), name="catalogue"),
    path("<slug:slug>/", views.TaskDetailView.as_view(), name="task_detail"),
    path("<slug:slug>/starten/", views.StartTaskView.as_view(), name="start"),
]
