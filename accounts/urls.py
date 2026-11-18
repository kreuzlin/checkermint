from django.urls import path, re_path

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
    path("profil/", views.ProfileEditView.as_view(), name="profile_edit"),
    path(
        "profil/roboter-wuerfeln/",
        views.RollAvatarView.as_view(),
        name="roll_avatar",
    ),
    re_path(
        r"^avatar/(?P<seed>[0-9a-f]{8,32})-(?P<size>64|128|256)\.png$",
        views.avatar,
        name="avatar",
    ),
    path(
        "teilnehmende/",
        views.ParticipantListView.as_view(),
        name="participant_list",
    ),
    path(
        "teilnehmende/<str:nickname>/",
        views.ParticipantDetailView.as_view(),
        name="participant_detail",
    ),
]
