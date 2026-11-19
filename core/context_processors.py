"""Template context available on every page."""

from django.conf import settings
from django.urls import reverse

from accounts.roles import is_coach

from .navigation import MAIN_NAVIGATION


def site(request):
    current = request.resolver_match
    current_name = current.view_name if current else None
    logged_in = request.user.is_authenticated
    coach = is_coach(request.user)
    nav_items = [
        {
            "label": item.label,
            "url": reverse(item.url_name),
            "active": item.url_name == current_name,
        }
        for item in MAIN_NAVIGATION
        if (logged_in or not item.members_only) and (coach or not item.coaches_only)
    ]
    return {
        "site_name": settings.SITE_NAME,
        "site_short_name": settings.SITE_SHORT_NAME,
        "site_description": settings.SITE_DESCRIPTION,
        "club_name": settings.CLUB_NAME,
        "privacy_email": settings.PRIVACY_EMAIL,
        "nav_items": nav_items,
    }
