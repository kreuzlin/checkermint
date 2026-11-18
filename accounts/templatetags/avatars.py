from django import template
from django.urls import reverse
from django.utils.html import format_html

from accounts.avatars import CREDITS, SIZES

register = template.Library()


@register.simple_tag
def avatar(profile, size=64, alt=""):
    """Robot avatar of `profile`, shown at `size` CSS pixels.

    The image is rendered at twice the size for high-density screens.
    `alt` stays empty when the nickname is next to the image (decorative).
    """
    pixels = min((s for s in SIZES if s >= size * 2), default=SIZES[-1])
    url = reverse(
        "accounts:avatar", kwargs={"seed": profile.avatar_seed, "size": pixels}
    )
    return format_html(
        '<img src="{}" width="{}" height="{}" alt="{}" class="avatar" loading="lazy">',
        url,
        size,
        size,
        alt,
    )


@register.inclusion_tag("accounts/_avatar_credits.html")
def avatar_credits():
    """Attribution for the avatar artwork (CC-BY, ADR 0012)."""
    return {"credits": CREDITS}
