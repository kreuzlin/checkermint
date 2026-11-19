from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .roles import is_coach


class CoachRequiredMixin(LoginRequiredMixin):
    """Coach views: login required, then 403 for everyone but coaches."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_coach(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
