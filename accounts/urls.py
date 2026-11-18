from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("anmelden/", views.LoginView.as_view(), name="login"),
    path("abmelden/", views.LogoutView.as_view(), name="logout"),
    path(
        "passwort-vergessen/",
        views.PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "passwort-vergessen/gesendet/",
        views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "passwort-neu/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "passwort-neu/fertig/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
