"""Nothing on the site may be indexed by search engines (brief, 4.7)."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class NoIndexTests(TestCase):
    def assert_noindex_header(self, response):
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_header_on_home_page(self):
        self.assert_noindex_header(self.client.get(reverse("core:home")))

    def test_header_on_version_endpoint(self):
        self.assert_noindex_header(self.client.get(reverse("core:version")))

    def test_header_on_admin_login(self):
        self.assert_noindex_header(self.client.get(reverse("admin:login")))

    def test_header_on_logged_in_admin(self):
        user = get_user_model().objects.create_superuser("admin", password="x")
        self.client.force_login(user)
        self.assert_noindex_header(self.client.get(reverse("admin:index")))

    @override_settings(DEBUG=False)
    def test_header_on_404(self):
        response = self.client.get("/gibt-es-nicht/")
        self.assertEqual(response.status_code, 404)
        self.assert_noindex_header(response)

    def test_meta_robots_tag_in_layout(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(
            response, '<meta name="robots" content="noindex, nofollow">', html=True
        )

    def test_no_canonical_or_open_graph_tags(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, 'rel="canonical"')
        self.assertNotContains(response, 'property="og:')


class RobotsTxtTests(TestCase):
    def test_disallows_everything(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response.content.decode(), "User-agent: *\nDisallow: /\n")

    def test_no_sitemap_url(self):
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 404)
