"""Startup check: the request limit in Caddy must allow one file of the
largest size (brief 5.7). Both values come from .env."""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def upload_limits(app_configs, **kwargs):
    largest_file = max(settings.UPLOAD_MAX_PHOTO_MB, settings.UPLOAD_MAX_FILE_MB)
    if largest_file > settings.UPLOAD_MAX_REQUEST_MB:
        return [
            Warning(
                f"UPLOAD_MAX_REQUEST_MB ({settings.UPLOAD_MAX_REQUEST_MB}) is smaller "
                f"than the largest file limit ({largest_file} MB).",
                hint="Raise UPLOAD_MAX_REQUEST_MB in .env and recreate caddy, "
                "or lower UPLOAD_MAX_PHOTO_MB / UPLOAD_MAX_FILE_MB.",
                id="submissions.W001",
            )
        ]
    return []
