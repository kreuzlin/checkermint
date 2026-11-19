"""Privacy page and imprint (brief 4.8, #47)."""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class LegalPagesTests(TestCase):
    def test_privacy_page(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertContains(response, "<title>Datenschutz – ")
        self.assertContains(response, settings.CLUB_NAME)
        self.assertContains(response, f'href="mailto:{settings.PRIVACY_EMAIL}"')
        self.assertContains(response, "UpCloud, in einem Rechenzentrum in Deutschland")
        self.assertContains(response, "Stand:")

    def test_imprint_with_avatar_credits(self):
        response = self.client.get(reverse("core:imprint"))
        self.assertContains(response, "<title>Impressum – ")
        self.assertContains(response, settings.CLUB_NAME)
        self.assertContains(response, 'href="https://vrobot.ch"')
        self.assertContains(response, "CC BY 4.0", count=2)  # page and footer

    def test_footer_links_on_every_page(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, f'href="{reverse("core:privacy")}"')
        self.assertContains(response, f'href="{reverse("core:imprint")}"')

    def test_swiss_spelling(self):
        for name in ("core:privacy", "core:imprint"):
            self.assertNotContains(self.client.get(reverse(name)), "ß")
