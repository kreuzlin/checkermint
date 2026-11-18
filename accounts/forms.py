from django import forms
from django.contrib.auth import forms as auth_forms


class LoginForm(auth_forms.AuthenticationForm):
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


class PasswordResetForm(auth_forms.PasswordResetForm):
    """Request a reset link (brief 5.1).

    Django sends the email only to active users with this address and a
    usable password; the response is the same whether or not an account
    matches, so the form does not reveal which addresses exist.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "E-Mail-Adresse"


class SetPasswordForm(auth_forms.SetPasswordForm):
    """New password from a reset link; role-based minimum length applies."""

    # Swiss spelling, own wording.
    error_messages = {
        "password_mismatch": "Die beiden Passwörter stimmen nicht überein.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Neues Passwort"
        self.fields["new_password2"].label = "Neues Passwort wiederholen"
        self.fields[
            "new_password2"
        ].help_text = "Zur Kontrolle noch einmal dasselbe Passwort."
