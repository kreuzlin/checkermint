"""Robot avatars with Robohash set1 (brief 5.2, ADR 0012, issue #14)."""

import hashlib
import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.avatars import CREDITS, SIZES, render_avatar
from accounts.models import Profile

User = get_user_model()

# Pixel hashes of a few seeds at 64 px. If a package upgrade (robohash,
# Pillow) changes them, every participant's avatar would change: check
# before updating these values (ADR 0012).
SNAPSHOTS = {
    "0123456789abcdef": "6ab2d79490253d0930483ebe5cd4526cd1a9311319ea869561e30f42f2d4d626",
    "cafe00112233beef": "be05e57ddd2e033d84a04c2f03f4eebaa65d373ceec3113549b5246e9ef5bd00",
    "5eed5eed5eed5eed": "b9c97d0310007e0b4398268224714898335166af1f944d10d8dcccf9af3581df",
}


def pixels_hash(png: bytes) -> str:
    return hashlib.sha256(Image.open(io.BytesIO(png)).tobytes()).hexdigest()


class RenderAvatarTests(TestCase):
    def test_snapshots_are_stable(self):
        for seed, expected in SNAPSHOTS.items():
            with self.subTest(seed=seed):
                self.assertEqual(pixels_hash(render_avatar(seed, 64)), expected)

    def test_sizes(self):
        for size in SIZES:
            image = Image.open(io.BytesIO(render_avatar("0123456789abcdef", size)))
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (size, size))

    def test_unsupported_size_is_rejected(self):
        with self.assertRaises(ValueError):
            render_avatar("0123456789abcdef", 300)

    def test_only_set1_is_used(self):
        with mock.patch("accounts.avatars.Robohash") as robohash:
            robohash.return_value.img = Image.new("RGBA", (64, 64))
            render_avatar("aaaaaaaaaaaaaaaa", 64)
        robohash.return_value.assemble.assert_called_once_with(
            roboset="set1", sizex=64, sizey=64
        )


class AvatarViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="Roboter-77")
        self.profile = Profile.objects.create(
            user=self.user,
            nickname="Robo-Anna",
            real_name="A",
            avatar_seed="0123456789abcdef",
        )

    def url(self, seed="0123456789abcdef", size=128):
        return reverse("accounts:avatar", kwargs={"seed": seed, "size": size})

    def test_png_is_public_and_cached_long(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("immutable", response["Cache-Control"])
        self.assertIn("public", response["Cache-Control"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_unknown_seed_is_not_rendered(self):
        response = self.client.get(self.url(seed="ffffffffffffffff"))
        self.assertEqual(response.status_code, 404)

    def test_other_sizes_and_seed_formats_do_not_resolve(self):
        for path in ("/avatar/0123456789abcdef-300.png", "/avatar/../etc-64.png"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_url_uses_seed_not_nickname(self):
        self.assertNotIn("anna", self.url().lower())


class RollAvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="Roboter-77")
        self.profile = Profile.objects.create(
            user=self.user, nickname="Robo-Anna", real_name="A"
        )
        self.url = reverse("accounts:roll_avatar")

    def test_roll_sets_new_seed(self):
        self.client.force_login(self.user)
        old_seed = self.profile.avatar_seed
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, reverse("accounts:profile_edit") + "#avatar")
        self.assertContains(response, "neuer Roboter")
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.avatar_seed, old_seed)
        # The new avatar renders.
        response = self.client.get(
            reverse(
                "accounts:avatar", kwargs={"seed": self.profile.avatar_seed, "size": 64}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_roll_is_post_only_and_needs_login(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        response = self.client.post(self.url)
        self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_profile_page_shows_avatar_and_roll_button(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertContains(response, "Neuen Roboter würfeln")
        self.assertContains(response, f"/avatar/{self.profile.avatar_seed}-256.png")
        self.assertContains(response, 'alt="Dein Roboter-Avatar"')

    def test_directory_shows_avatar(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:participant_list"))
        self.assertContains(response, f"/avatar/{self.profile.avatar_seed}-64.png")


class CreditsTests(TestCase):
    def test_footer_credits_artwork(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'id="avatar-credits"')
        for key in ("work", "author", "license", "license_url", "source_url"):
            self.assertContains(response, CREDITS[key])
        self.assertEqual(CREDITS["author"], "Zikri Kader")
