from rest_framework import authentication, exceptions
from django.utils import timezone

from accounts.models import IMPORT_TOKEN_PREFIX


class ImportTokenAuthentication(authentication.BaseAuthentication):
    """Authenticates an agent-import submission via a scoped `himp_` bearer token.

    Deliberately used ONLY on the agent-import endpoints (set explicitly via
    `authentication_classes`). Every other endpoint keeps the default
    JWTAuthentication, so an import token grants access to nothing but the
    import endpoints — that is the entire scoping mechanism.

    Returns None (rather than raising) when the header is missing or is clearly
    not an import token, so it never interferes with other auth schemes.
    """
    keyword = b'bearer'

    def authenticate(self, request):
        # Imported lazily to avoid an app-registry import cycle at startup.
        from accounts.models import AgentImportConfig

        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword:
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed('Invalid authorization header.')

        token = header[1].decode('latin-1')
        if not token.startswith(IMPORT_TOKEN_PREFIX):
            # Not ours (likely a JWT) — let it fall through / be rejected elsewhere.
            return None

        try:
            config = AgentImportConfig.objects.select_related('user').get(token=token)
        except AgentImportConfig.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or revoked import token.')

        if not config.user.is_active:
            raise exceptions.AuthenticationFailed('User account is inactive.')

        # Best-effort usage stamp; never block the request on it.
        config.last_used_at = timezone.now()
        config.save(update_fields=['last_used_at'])

        return (config.user, config)

    def authenticate_header(self, request):
        # Drives the WWW-Authenticate header so failures return 401 (not 403).
        return 'Bearer'
