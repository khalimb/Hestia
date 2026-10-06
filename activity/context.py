"""Who is acting, and through which door — carried per request so the
shared write paths (serializers, delete helpers) can log without every
caller threading actor/source arguments through.

Two layers: the middleware stores the HttpRequest (actor resolved lazily,
after DRF authentication has run); the MCP endpoint pushes an explicit
actor/source/token/session on top for the duration of a call.
"""
import contextvars
from contextlib import contextmanager

_context = contextvars.ContextVar('activity_context', default=None)


@contextmanager
def activity_context(**values):
    token = _context.set(values)
    try:
        yield
    finally:
        _context.reset(token)


def current_context():
    return _context.get() or {}


def resolve_actor_and_source():
    """-> (actor_user_or_None, source, token_or_None, session_or_None)."""
    from .models import ActivityLog
    ctx = current_context()
    if 'actor' in ctx:            # explicit (MCP endpoint, scripts)
        return (ctx.get('actor'), ctx.get('source', ActivityLog.SOURCE_SYSTEM),
                ctx.get('token'), ctx.get('session'))
    request = ctx.get('request')
    if request is None:
        return None, ActivityLog.SOURCE_SYSTEM, None, None
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        user = None
    # DRF mirrors request.auth onto the underlying HttpRequest; the agent
    # import authenticator sets it to the AgentImportConfig row.
    auth = getattr(request, 'auth', None)
    source = ActivityLog.SOURCE_IMPORT if type(auth).__name__ == 'AgentImportConfig' \
        else ActivityLog.SOURCE_WEB
    return user, source, None, None
