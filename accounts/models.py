import secrets
import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

# Import tokens are prefixed so the custom authenticator can cheaply tell them
# apart from JWTs (which it must ignore) without a DB hit.
IMPORT_TOKEN_PREFIX = 'himp_'


def generate_import_token():
    return f"{IMPORT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name']

    def __str__(self):
        return self.email


class AgentImportConfig(models.Model):
    """Per-user configuration for the 'export a prompt to an agent' import flow.

    Holds a dedicated, revocable submission token (scoped to creating expenses
    and reading import options only) and the user's editable prompt template.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='agent_import_config',
    )
    # Null = no active token (never generated, or revoked).
    token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True,
    )
    # Blank = use the system default template (see import_prompt.DEFAULT_PROMPT_TEMPLATE).
    prompt_template = models.TextField(blank=True, default='')
    token_created_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AgentImportConfig({self.user})"

    @property
    def has_token(self):
        return bool(self.token)

    @property
    def token_masked(self):
        """A display-safe hint of the token, e.g. 'himp_…a1b2'. Never the full value."""
        if not self.token:
            return None
        return f"{IMPORT_TOKEN_PREFIX}…{self.token[-4:]}"
