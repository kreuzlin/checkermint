"""Test runner with a fast password hasher (issue #117).

Django's default PBKDF2 hasher is slow on purpose (1,000,000 iterations).
Tests create many users, so hashing took about 85 % of the test time. While
tests run, this runner switches to the MD5 hasher. The live site never
uses this runner: Django only reads TEST_RUNNER in `manage.py test`.
"""

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

TEST_PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


class FastPasswordHasherRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # override_settings also clears Django's cached hasher list.
        self._fast_hashers = override_settings(PASSWORD_HASHERS=TEST_PASSWORD_HASHERS)
        self._fast_hashers.enable()

    def teardown_test_environment(self, **kwargs):
        self._fast_hashers.disable()
        super().teardown_test_environment(**kwargs)
