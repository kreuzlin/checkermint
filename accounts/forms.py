from django import forms
from django.contrib.auth import forms as auth_forms
from django.core.validators import MaxLengthValidator

from .models import Profile


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


class ProfileForm(forms.ModelForm):
    """The participant's own profile (brief 5.1, 4.5 and 4.6).

    Nickname and real name are set by a coach; the email address lives on
    the user and is only visible to the user and to coaches.
    """

    ABOUT_MAX_LENGTH = 1000

    email = forms.EmailField(
        label="E-Mail-Adresse",
        required=False,
        help_text=(
            "Freiwillig. Nur du und die Coaches sehen sie. Damit kannst du "
            "ein vergessenes Passwort selbst zurücksetzen und bekommst "
            "Benachrichtigungen."
        ),
    )

    class Meta:
        model = Profile
        fields = [
            "about",
            "show_about",
            "show_badges",
            "show_solved_tasks",
            "email_notifications",
        ]
        widgets = {"about": forms.Textarea(attrs={"rows": 6})}
        help_texts = {
            "about": (
                "Ein paar Sätze über dich, zum Beispiel was du gerne baust. "
                "Kein echter Name, keine Adresse. **fett**, *kursiv* und "
                "Listen gehen."
            ),
            "email_notifications": (
                "Wenn eine E-Mail-Adresse hinterlegt ist: Nachricht, wenn deine "
                "Einreichung angeschaut wurde oder ein Coach auf deine "
                "Hinweis-Anfrage antwortet."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["about"].max_length = self.ABOUT_MAX_LENGTH
        self.fields["about"].validators.append(
            MaxLengthValidator(self.ABOUT_MAX_LENGTH)
        )
        self.fields["email"].initial = self.instance.user.email
        # Email first, then the text, then the switches.
        self.order_fields(["email", "about"])

    def save(self, commit=True):
        profile = super().save(commit=commit)
        user = profile.user
        user.email = self.cleaned_data["email"]
        if commit:
            user.save(update_fields=["email"])
        return profile
