"""Tests for the base layout and SEO tags."""

from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.views.generic import TemplateView

from core.seo import SeoMixin, build_title


@override_settings(SITE_TITLE="Kurz – Langer Name", SITE_SHORT_NAME="Kurz")
class BuildTitleTests(SimpleTestCase):
    def test_without_page_title_uses_site_title(self):
        self.assertEqual(build_title(), "Kurz – Langer Name")

    def test_with_page_title_appends_short_name(self):
        self.assertEqual(build_title("Kontakt"), "Kontakt – Kurz")


class SeoMixinTests(SimpleTestCase):
    def test_puts_title_and_description_into_context(self):
        class View(SeoMixin, TemplateView):
            template_name = "base.html"
            page_title = "Kontakt"
            meta_description = "So erreichen Sie uns"

        view = View()
        view.setup(RequestFactory().get("/"))
        context = view.get_context_data()

        self.assertEqual(context["page_title"], "Kontakt")
        self.assertEqual(context["meta_description"], "So erreichen Sie uns")


class HomePageTests(TestCase):
    def setUp(self):
        self.response = self.client.get(reverse("core:home"))

    def test_renders(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertTemplateUsed(self.response, "core/home.html")

    def test_title_and_meta_description(self):
        self.assertContains(
            self.response, f"<title>{settings.SITE_TITLE}</title>", html=True
        )
        self.assertContains(
            self.response,
            f'<meta name="description" content="{settings.SITE_DESCRIPTION}">',
            html=True,
        )

    def test_language_is_swiss_german(self):
        self.assertContains(self.response, '<html lang="de-ch">')

    def test_brand_links_home_and_marks_current_page(self):
        self.assertContains(
            self.response,
            f'<a class="brand" href="{reverse("core:home")}" aria-current="page">',
        )

    def test_header_shows_logo_with_alt_text(self):
        self.assertContains(self.response, "core/brand/logo-header.svg")
        self.assertContains(self.response, f'alt="{settings.SITE_SHORT_NAME}"')

    def test_favicons_are_linked(self):
        self.assertContains(
            self.response, 'rel="icon" href="/static/core/brand/icon.svg"'
        )
        self.assertContains(self.response, "core/brand/favicon-32.png")
        self.assertContains(self.response, 'rel="apple-touch-icon"')


class BrandAssetTests(SimpleTestCase):
    """The generated logo files exist (design/generate_assets.py)."""

    def test_generated_files_exist(self):
        for name in (
            "logo-header.svg",
            "icon.svg",
            "favicon-32.png",
            "apple-touch-icon.png",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(finders.find(f"core/brand/{name}"))

    def test_svgs_contain_no_editor_metadata_or_scripts(self):
        for name in ("logo-header.svg", "icon.svg"):
            with self.subTest(name=name):
                content = Path(finders.find(f"core/brand/{name}")).read_text()
                self.assertNotIn("inkscape", content)
                self.assertNotIn("sodipodi", content)
                self.assertNotIn("<script", content)


class ErrorPageTests(TestCase):
    @override_settings(DEBUG=False)
    def test_404_page_is_german(self):
        response = self.client.get("/gibt-es-nicht/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Seite nicht gefunden", status_code=404)
        self.assertContains(
            response,
            f"<title>Seite nicht gefunden – {settings.SITE_SHORT_NAME}</title>",
            status_code=404,
        )
