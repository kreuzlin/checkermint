"""Upload limits are consistent (#25)."""

from django.test import SimpleTestCase, override_settings

from submissions.checks import upload_limits


class UploadLimitCheckTests(SimpleTestCase):
    @override_settings(
        UPLOAD_MAX_PHOTO_MB=15, UPLOAD_MAX_FILE_MB=20, UPLOAD_MAX_REQUEST_MB=100
    )
    def test_defaults_are_consistent(self):
        self.assertEqual(upload_limits(None), [])

    @override_settings(
        UPLOAD_MAX_PHOTO_MB=15, UPLOAD_MAX_FILE_MB=20, UPLOAD_MAX_REQUEST_MB=10
    )
    def test_request_limit_below_a_file_limit_warns(self):
        warnings = upload_limits(None)
        self.assertEqual([w.id for w in warnings], ["submissions.W001"])
