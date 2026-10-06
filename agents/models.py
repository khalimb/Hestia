"""Agent access to Hestia: MCP tokens, sessions, and per-user prompt config.

Modelled on Hierophant's mcp_gateway:

- McpToken   — unguessable token in the connector URL (/mcp/<token>/). Per
               user, so writes made through MCP are attributed to the owner.
               Revoke by deleting the row.
- McpSession — one client session (Mcp-Session-Id), for reviewing what an
               agent did (see the activity app).
- AgentConfig — per-user override of the agent prompt template.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

# Prefix lets the endpoint and the Settings UI recognise these tokens at a glance.
MCP_TOKEN_PREFIX = 'hmcp_'


def generate_mcp_token():
    return f"{MCP_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


class McpToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mcp_tokens',
    )
    # Which client this token is for, e.g. "claude.ai" or "Claude Code (laptop)".
    name = models.CharField(max_length=100)
    token = models.CharField(max_length=64, unique=True, default=generate_mcp_token)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"McpToken {self.name} ({self.user})"

    @property
    def token_masked(self):
        """Display-safe hint, e.g. 'hmcp_…a1b2'. Never the full value."""
        return f"{MCP_TOKEN_PREFIX}…{self.token[-4:]}"


class McpSession(models.Model):
    """One MCP client session (Mcp-Session-Id), minted on `initialize` and
    echoed back by the client on every later request. Groups the activity
    rows an agent produced so a session can be reviewed afterwards; also
    counts tool calls so reads (which log no activity rows) are visible."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(McpToken, on_delete=models.CASCADE, related_name='sessions')
    client_name = models.CharField(max_length=100, blank=True, default='')
    client_version = models.CharField(max_length=50, blank=True, default='')
    protocol_version = models.CharField(max_length=20, blank=True, default='')
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    request_count = models.PositiveIntegerField(default=0)
    # {tool_name: call_count}, including reads.
    tool_calls = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"McpSession {self.client_name or '?'} via {self.token.name}"

    def note_tool_call(self, name):
        self.tool_calls[name] = self.tool_calls.get(name, 0) + 1


class AgentConfig(models.Model):
    """Per-user agent settings. Blank template = use the system default."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_config',
    )
    prompt_template = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AgentConfig({self.user})"
