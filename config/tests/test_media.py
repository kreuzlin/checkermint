"""Uploaded files are never served from a public URL (ADR 0009)."""

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve


class NoPublicMediaUrlTests(SimpleTestCase):
    def test_media_path_is_not_routed(self):
        with self.assertRaises(Resolver404):
            resolve("/media/submissions/photo.jpg")
