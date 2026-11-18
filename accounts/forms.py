from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """Login with an optional "remember me" (brief, sections 5.1 and 11)."""

    # Swiss spelling (Django's German translation uses «ß»).
    error_messages = {
        "invalid_login": (
            "Benutzername oder Passwort stimmt nicht. Achte auf Gross- und "
            "Kleinschreibung."
        ),
        "inactive": "Dieses Konto ist deaktiviert. Bitte wende dich an einen Coach.",
    }

    remember_me = forms.BooleanField(
        label="Angemeldet bleiben",
        required=False,
        help_text="Nur auf deinem eigenen Gerät ankreuzen (30 Tage).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Benutzername"
        self.fields["password"].label = "Passwort"
