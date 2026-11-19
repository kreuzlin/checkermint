"""Public landing page for visitors (brief 5.12, #45)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile

User = get_user_model()


class LandingPageTests(TestCase):
    def setUp(self):
        self.url = reverse("core:home")

    def test_visitors_see_what_checkermint_is(self):
        response = self.client.get(self.url)
        self.assertContains(response, "So funktioniert’s")
        self.assertContains(response, '<a href="https://vrobot.ch">vrobot.ch</a>')
        self.assertContains(
            response,
            f'<a class="button" href="{reverse("accounts:login")}">Anmelden</a>',
            html=True,
        )

    def test_no_images_and_no_participant_data(self):
        user = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=user, nickname="RoboAnna", real_name="Anna M")
        response = self.client.get(self.url)
        content = response.content.decode()
        main = content[content.index("<main") : content.index("</main>")]
        self.assertNotIn("<img", main)
        self.assertNotIn("RoboAnna", content)
        self.assertNotIn("Anna M", content)

    def test_logged_in_users_get_their_page_instead(self):
        user = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=user, nickname="RoboAnna")
        self.client.force_login(user)
        self.assertNotContains(self.client.get(self.url), "So funktioniert’s")
