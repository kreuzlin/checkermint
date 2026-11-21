"""The fast test hasher never reaches the live site (#117)."""

import importlib

from django.conf import global_settings, settings
from django.contrib.auth.hashers import get_hasher, make_password
from django.test import SimpleTestCase

WEAK_HASHERS = {
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "django.contrib.auth.hashers.UnsaltedMD5PasswordHasher",
    "django.contrib.auth.hashers.UnsaltedSHA1PasswordHasher",
    "django.contrib.auth.hashers.SHA1PasswordHasher",
}


class LiveHasherTests(SimpleTestCase):
    def live_hashers(self):
        # The settings module as the live site loads it, not the
        # test-time override of django.conf.settings.
        module = importlib.import_module("config.settings")
        return getattr(module, "PASSWORD_HASHERS", global_settings.PASSWORD_HASHERS)

    def test_live_site_hashes_with_pbkdf2(self):
        self.assertEqual(
            self.live_hashers()[0],
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
        )

    def test_live_site_has_no_weak_hasher(self):
        self.assertFalse(WEAK_HASHERS & set(self.live_hashers()))

    def test_fast_hasher_only_through_the_test_runner(self):
        self.assertEqual(
            settings.TEST_RUNNER, "config.test_runner.FastPasswordHasherRunner"
        )
        self.assertEqual(get_hasher().algorithm, "md5")
        self.assertTrue(make_password("geheim").startswith("md5$"))
