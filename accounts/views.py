from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

from core.seo import SeoMixin

from .forms import LoginForm, PasswordResetForm, SetPasswordForm


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
