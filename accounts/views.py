from django.conf import settings
from django.contrib.auth import views as auth_views

from core.seo import SeoMixin

from .forms import LoginForm


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
