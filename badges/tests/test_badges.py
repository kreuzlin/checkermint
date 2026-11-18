"""Badges with static artwork or a placeholder (brief 5.8, issue #15)."""

import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from badges import models as badge_models
from badges.models import Badge

User = get_user_model()


class BadgeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        image_dir = Path(self.tmp.name)
        (image_dir / "zahnrad.svg").write_text("<svg/>")
        (image_dir / "notes.txt").write_text("x")
        patcher = mock.patch.object(badge_models, "IMAGE_DIR", image_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_available_images_lists_image_files_only(self):
        self.assertEqual(badge_models.available_images(), ["zahnrad.svg"])

    def test_placeholder_without_image(self):
        badge = Badge(name="Erster Roboter")
        badge.full_clean()
        self.assertIsNone(badge.image_url)

    def test_image_must_exist(self):
        with self.assertRaises(ValidationError):
            Badge(name="X", image="fehlt.png").full_clean()
        badge = Badge(name="Zahnrad", image="zahnrad.svg")
        badge.full_clean()
        self.assertTrue(badge.image_url.endswith("badges/img/zahnrad.svg"))

    def test_admin_offers_available_images(self):
        admin = User.objects.create_superuser("chef", password="Roboter-777")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:badges_badge_add"))
        self.assertContains(response, '<option value="zahnrad.svg">')
        self.assertContains(response, "Platzhalter")
        response = self.client.post(
            reverse("admin:badges_badge_add"),
            {"name": "Zahnrad", "description": "", "image": "zahnrad.svg"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Badge.objects.get().image, "zahnrad.svg")
