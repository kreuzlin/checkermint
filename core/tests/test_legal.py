"""Privacy page and imprint (brief 4.8, #47)."""

from django.conf import settings
from django.test import TestCase, override_settings
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

    def test_imprint_names_the_gearsbot_version(self):
        """GPLv3 attribution with the pinned commit (ADR 0022)."""
        sha = (settings.BASE_DIR / "sim" / "gears" / "UPSTREAM").read_text().strip()
        response = self.client.get(reverse("core:imprint"))
        self.assertContains(response, "GNU General Public License v3")
        self.assertContains(
            response, f"https://github.com/QuirkyCort/gears/commit/{sha}"
        )
        self.assertContains(response, f"<code>{sha[:12]}</code>")

    @override_settings(GEARSBOT_COMMIT="")
    def test_imprint_without_gearsbot(self):
        response = self.client.get(reverse("core:imprint"))
        self.assertNotContains(response, "GearsBot")

    @override_settings(SIMULATOR_URL="https://sim.example.ch")
    def test_privacy_mentions_the_simulator_when_configured(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertContains(response, "<h2>Simulator</h2>", html=False)
        self.assertContains(response, "<strong>sim.example.ch</strong>")
        self.assertContains(response, "nur im Browser des Geräts")

    @override_settings(SIMULATOR_URL="")
    def test_privacy_without_simulator(self):
        response = self.client.get(reverse("core:privacy"))
        self.assertNotContains(response, "<h2>Simulator</h2>", html=False)
