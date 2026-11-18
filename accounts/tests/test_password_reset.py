"""Password reset by email (brief 5.1, issue #12)."""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile

User = get_user_model()


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "anna", email="anna@example.com", password="Roboter-77"
        )
        Profile.objects.create(user=self.user, nickname="Robo-Anna", real_name="A")
        self.url = reverse("accounts:password_reset")

    def request_link(self, email="anna@example.com"):
        return self.client.post(self.url, {"email": email})

    def reset_link(self):
        match = re.search(r"https?://\S+/passwort-neu/\S+/", mail.outbox[0].body)
        self.assertIsNotNone(match)
        return match.group(0)

    def test_login_page_links_to_reset(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, self.url)

    def test_form_page_in_german(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Passwort vergessen – Checkermint</title>")
        self.assertContains(response, "E-Mail-Adresse")

    def test_sends_german_email_with_link_and_username(self):
        response = self.request_link()
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["anna@example.com"])
        self.assertEqual(message.subject, "Neues Passwort für Checkermint")
        self.assertIn("Hallo Robo-Anna", message.body)
        self.assertIn("Dein Benutzername: anna", message.body)
        self.assertIn("3 Tage gültig", message.body)
        self.assertNotIn("ß", message.subject + message.body)

    def test_email_match_ignores_case(self):
        self.request_link("Anna@Example.COM")
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_address_looks_the_same_and_sends_nothing(self):
        response = self.request_link("niemand@example.com")
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        response = self.client.get(reverse("accounts:password_reset_done"))
        self.assertContains(response, "Wenn ein Konto mit dieser E-Mail-Adresse")
        self.assertContains(response, "3 Tage gültig")
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_user_gets_no_email(self):
        self.user.is_active = False
        self.user.save()
        self.request_link()
        self.assertEqual(len(mail.outbox), 0)

    def test_user_without_email_cannot_be_reset_by_email(self):
        User.objects.create_user("ben", password="Roboter-77")
        self.request_link("")
        self.assertEqual(len(mail.outbox), 0)

    def test_full_flow_sets_new_password(self):
        self.request_link()
        response = self.client.get(self.reset_link(), follow=True)
        self.assertContains(response, "Neues Passwort setzen")
        set_url = response.redirect_chain[-1][0]
        response = self.client.post(
            set_url,
            {"new_password1": "Turbo-42x", "new_password2": "Turbo-42x"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Turbo-42x"))

        # The link works only once.
        response = self.client.get(self.reset_link(), follow=True)
        self.assertContains(response, "Link ungültig")

    def test_participant_minimum_length_and_mismatch(self):
        self.request_link()
        response = self.client.get(self.reset_link(), follow=True)
        set_url = response.redirect_chain[-1][0]

        response = self.client.post(
            set_url, {"new_password1": "Ab-1x", "new_password2": "Ab-1x"}
        )
        self.assertContains(response, "mindestens 6 Zeichen")

        response = self.client.post(
            set_url, {"new_password1": "Turbo-42x", "new_password2": "Turbo-43x"}
        )
        self.assertContains(response, "stimmen nicht überein")
        self.assertNotContains(response, "ß")

        # Six characters are enough for a participant.
        response = self.client.post(
            set_url, {"new_password1": "Kx-7qz", "new_password2": "Kx-7qz"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

    def test_invalid_token_shows_german_message(self):
        url = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": "MQ", "token": "abc-def"},
        )
        response = self.client.get(url)
        self.assertContains(response, "Link ungültig")

    def test_pages_are_noindex(self):
        response = self.client.get(self.url)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
