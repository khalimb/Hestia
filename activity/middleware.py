from .context import activity_context


class ActivityContextMiddleware:
    """Make the current request reachable from the write paths (see
    activity.context). Actor is read lazily at record time, after DRF auth."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with activity_context(request=request):
            return self.get_response(request)
