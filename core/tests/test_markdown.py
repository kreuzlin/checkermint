"""Markdown is rendered and sanitised (brief, 8.8)."""

from django.template import Context, Template
from django.test import SimpleTestCase

from core.markdown import render_markdown


class RenderMarkdownTests(SimpleTestCase):
    def test_basic_formatting(self):
        html = render_markdown("Hallo **Welt** und *du*")
        self.assertEqual(html, "<p>Hallo <strong>Welt</strong> und <em>du</em></p>")

    def test_lists_code_and_tables(self):
        html = render_markdown(
            "- eins\n- zwei\n\n```\nprint('x')\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |"
        )
        self.assertIn("<ul>", html)
        self.assertIn("<pre><code>print('x')", html)
        self.assertIn("<table>", html)

    def test_html_in_code_block_is_shown_as_text(self):
        html = render_markdown("```\n<script>alert(1)</script>\n```")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script", html)

    def test_h1_becomes_h2(self):
        self.assertEqual(render_markdown("# Titel"), "<h2>Titel</h2>")

    def test_empty_input(self):
        self.assertEqual(render_markdown(""), "")

    def test_raw_html_script_is_removed(self):
        html = render_markdown("Text <script>alert(1)</script> mehr")
        self.assertNotIn("<script", html)
        self.assertNotIn("alert(1)", html)

    def test_event_handler_attributes_are_removed(self):
        html = render_markdown('<p onclick="alert(1)">x</p>')
        self.assertNotIn("onclick", html)

    def test_iframe_and_style_are_removed(self):
        html = render_markdown(
            '<iframe src="https://example.com"></iframe><style>p{}</style>'
        )
        self.assertNotIn("<iframe", html)
        self.assertNotIn("<style", html)

    def test_javascript_link_is_neutralised(self):
        html = render_markdown("[klick](javascript:alert(1))")
        self.assertNotIn("javascript:", html)

    def test_links_get_safe_rel(self):
        html = render_markdown("[VRoboT](https://vrobot.ch)")
        self.assertIn('href="https://vrobot.ch"', html)
        self.assertIn('rel="noopener noreferrer nofollow"', html)

    def test_relative_links_are_kept(self):
        self.assertIn('href="/aufgaben/"', render_markdown("[Aufgaben](/aufgaben/)"))

    def test_images_are_not_rendered(self):
        html = render_markdown("![Bild](https://tracker.example.com/pixel.png)")
        self.assertNotIn("<img", html)
        self.assertNotIn("tracker.example.com", html.replace("Bild", ""))


class MarkdownFilterTests(SimpleTestCase):
    def render(self, value):
        template = Template("{% load markdown %}{{ value|markdown }}")
        return template.render(Context({"value": value}))

    def test_renders_html_unescaped(self):
        self.assertEqual(self.render("**fett**"), "<p><strong>fett</strong></p>")

    def test_none_renders_empty(self):
        self.assertEqual(self.render(None), "")

    def test_script_never_reaches_output(self):
        self.assertNotIn("<script", self.render("<script>alert(1)</script>"))


class MarkdownImageTests(SimpleTestCase):
    def setUp(self):
        from core.markdown import ImageRef

        self.images = {
            12: ImageRef(
                url="/dateien/anleitungsbild/12/", alt="Sensor", width=40, height=20
            )
        }

    def render(self, text, images=None):
        from core.markdown import render_markdown

        return render_markdown(text, images=images)

    def test_without_images_mapping_images_are_removed(self):
        html = self.render("![x](bild:12) ![y](https://example.com/a.png)")
        self.assertNotIn("<img", html)

    def test_own_image_becomes_private_url(self):
        html = self.render("Schau: ![egal](bild:12)", self.images)
        self.assertIn(
            '<img src="/dateien/anleitungsbild/12/" alt="Sensor" width="40" '
            'height="20" loading="lazy">',
            html,
        )

    def test_foreign_external_and_unknown_images_are_dropped(self):
        html = self.render(
            "![a](bild:99) ![b](https://example.com/a.png) ![c](/media/x.png) "
            '<img src="bild:12" onerror="alert(1)">',
            self.images,
        )
        self.assertEqual(html.count("[Bild fehlt]"), 3)
        self.assertNotIn("example.com", html)
        self.assertNotIn("/media/", html)
        self.assertNotIn("onerror", html)
