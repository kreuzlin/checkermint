"""Login, logout, session length and password rules (brief 5.1 and 11)."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile

User = get_user_model()
PASSWORD = "Roboter-77"


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password=PASSWORD)
        Profile.objects.create(user=self.user, nickname="Robo-Anna", real_name="A")
        self.url = reverse("accounts:login")

    def login(self, **extra):
        data = {"username": "anna", "password": PASSWORD, **extra}
        return self.client.post(self.url, data)

    def test_page_renders_in_german(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Anmelden – Checkermint</title>")
        self.assertContains(response, "Angemeldet bleiben")
        self.assertContains(response, "Benutzername")

    def test_login_redirects_home(self):
        response = self.login()
        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_respects_next(self):
        response = self.client.post(
            self.url + "?next=/admin/",
            {"username": "anna", "password": PASSWORD, "next": "/admin/"},
        )
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_external_next_is_ignored(self):
        response = self.login(next="https://example.com/")
        self.assertRedirects(response, reverse("core:home"))

    def test_without_remember_me_session_ends_with_browser(self):
        self.login()
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_remember_me_keeps_session_for_30_days(self):
        self.login(remember_me="on")
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), 30 * 24 * 60 * 60)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 30 * 24 * 60 * 60)

    def test_wrong_password_shows_swiss_german_error(self):
        response = self.login(password="falsch")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fehler:")
        self.assertContains(response, "Gross- und Kleinschreibung")
        self.assertNotContains(response, "ß")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logged_in_user_is_redirected_away_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("core:home"))

    def test_header_shows_login_link_or_nickname_and_logout(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, f'href="{self.url}"')
        self.assertNotContains(response, "Abmelden")

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Robo-Anna")
        self.assertContains(response, "Abmelden")

    def test_header_falls_back_to_username_without_profile(self):
        admin = User.objects.create_superuser("chef", password=PASSWORD)
        self.client.force_login(admin)
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, '<span class="user-name">chef</span>')

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        logout_url = reverse("accounts:logout")
        self.assertEqual(self.client.get(logout_url).status_code, 405)
        response = self.client.post(logout_url)
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordRuleTests(TestCase):
    def test_participant_needs_six_characters(self):
        participant = User(username="kind")
        validate_password("Robo42", participant)
        with self.assertRaises(ValidationError) as cm:
            validate_password("Rob42", participant)
        self.assertIn("mindestens 6 Zeichen", str(cm.exception))

    def test_staff_needs_eight_characters(self):
        coach = User(username="coach", is_staff=True)
        validate_password("Robo4242", coach)
        with self.assertRaises(ValidationError) as cm:
            validate_password("Robo424", coach)
        self.assertIn("mindestens 8 Zeichen", str(cm.exception))

    def test_unknown_user_gets_stricter_rule(self):
        with self.assertRaises(ValidationError):
            validate_password("Robo424", None)

    def test_other_django_validators_still_apply(self):
        with self.assertRaises(ValidationError):
            validate_password("123456", User(username="kind"))
