from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, UpdateView

from core.seo import SeoMixin

from .forms import LoginForm, PasswordResetForm, ProfileForm, SetPasswordForm
from .models import Profile
from .roles import is_coach


class LoginView(SeoMixin, auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True
    page_title = "Anmelden"
    meta_description = "Anmeldung für Teilnehmende und Coaches von Checkermint."

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            # Shared devices in the club: end the session with the browser.
            self.request.session.set_expiry(0)
        return response


class LogoutView(auth_views.LogoutView):
    """POST only (Django default); the header has a logout button."""


class PasswordResetContextMixin:
    """Validity of reset links in days, shown on the pages and in the email."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["timeout_days"] = password_reset_timeout_days()
        return context


def password_reset_timeout_days():
    return settings.PASSWORD_RESET_TIMEOUT // (60 * 60 * 24)


class PasswordResetView(SeoMixin, auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    form_class = PasswordResetForm
    subject_template_name = "accounts/email/password_reset_subject.txt"
    email_template_name = "accounts/email/password_reset_email.txt"
    success_url = reverse_lazy("accounts:password_reset_done")
    page_title = "Passwort vergessen"
    meta_description = "Neues Passwort für Checkermint per E-Mail anfordern."

    def get_extra_email_context(self):
        return {
            "site_name": settings.SITE_SHORT_NAME,
            "site_full_name": settings.SITE_NAME,
            "timeout_days": password_reset_timeout_days(),
        }

    def form_valid(self, form):
        self.extra_email_context = self.get_extra_email_context()
        return super().form_valid(form)


class PasswordResetDoneView(
    PasswordResetContextMixin, SeoMixin, auth_views.PasswordResetDoneView
):
    template_name = "accounts/password_reset_done.html"
    page_title = "E-Mail verschickt"
    meta_description = "Der Link für ein neues Passwort ist unterwegs."


class PasswordResetConfirmView(SeoMixin, auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")
    page_title = "Neues Passwort setzen"
    meta_description = "Neues Passwort für Checkermint setzen."


class PasswordResetCompleteView(SeoMixin, auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
    page_title = "Passwort geändert"
    meta_description = "Das neue Passwort ist gespeichert."


class ProfileEditView(LoginRequiredMixin, SeoMixin, SuccessMessageMixin, UpdateView):
    """Own profile: about text, email and visibility switches (brief 5.1)."""

    form_class = ProfileForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile_edit")
    success_message = "Dein Profil ist gespeichert."
    page_title = "Mein Profil"
    meta_description = "Eigenes Profil und Sichtbarkeit bearbeiten."

    def get(self, request, *args, **kwargs):
        if not Profile.objects.filter(user=request.user).exists():
            # Staff accounts without a profile (e.g. the admin).
            return render(
                request,
                "accounts/profile_missing.html",
                {"page_title": self.page_title},
            )
        return super().get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return get_object_or_404(Profile, user=self.request.user)


def participant_profiles():
    """Profiles of active participants (not staff); the internal directory."""
    return Profile.objects.filter(
        user__is_active=True, user__is_staff=False, user__is_superuser=False
    ).select_related("user")


class ParticipantListView(LoginRequiredMixin, SeoMixin, ListView):
    template_name = "accounts/participant_list.html"
    context_object_name = "profiles"
    page_title = "Teilnehmende"
    meta_description = "Alle Teilnehmenden von Checkermint."

    def get_queryset(self):
        return participant_profiles()


class ParticipantDetailView(LoginRequiredMixin, SeoMixin, DetailView):
    """Internal profile, for logged-in users only (brief, section 3).

    Shows the real name and the about text regardless of the visibility
    switches (those only control the public page). The email address only
    to the participant and to coaches (brief 4.5).
    """

    template_name = "accounts/participant_detail.html"
    context_object_name = "profile"
    meta_description = "Profil einer Teilnehmerin oder eines Teilnehmers."

    def get_object(self, queryset=None):
        return get_object_or_404(
            participant_profiles(), nickname__iexact=self.kwargs["nickname"]
        )

    def get_page_title(self):
        return self.object.nickname

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_own = self.object.user_id == user.pk
        context["is_own"] = is_own
        context["show_email"] = is_own or is_coach(user)
        return context
