"""Site-wide response middleware."""

ROBOTS_TAG = "noindex, nofollow"


class NoIndexMiddleware:
    """Tell search engines not to index or follow anything (brief, 4.7).

    Set on every response by Django itself, so it holds even without Caddy
    in front (e.g. a test on the server IP) and cannot be switched off by
    configuration.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["X-Robots-Tag"] = ROBOTS_TAG
        return response
