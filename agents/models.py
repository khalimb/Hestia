"""Agent access to Hestia: MCP tokens, assignments, and per-user prompt config.

Modelled on Hierophant's mcp_gateway + ProjectResearch (kind=ASG):

- McpToken      — unguessable token in the connector URL (/mcp/<token>/).
                  Per user, so writes made through MCP are attributed to the
                  token's owner. Revoke by deleting the row.
- Assignment    — one deliverable doc. The user starts it from the UI (copies
                  a rendered prompt), gives the brief in an agent session, and
                  the agent writes the deliverable back via the `assignment_save`
                  MCP tool or the content_token PATCH fallback.
- AgentConfig   — per-user override of the assignment prompt template.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

# Prefix lets the endpoint and the Settings UI recognise these tokens at a
# glance; it is distinct from the agent-import `himp_` prefix on purpose,
# since MCP tokens grant far broader access.
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


class Assignment(models.Model):
    STATUS_EMPTY = 'EMPTY'
    STATUS_POPULATED = 'POPUL'
    STATUS_CHOICES = [
        (STATUS_EMPTY, 'Awaiting deliverable'),
        (STATUS_POPULATED, 'Saved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignments',
    )
    # Optional topic captured at creation; labels the list and seeds the
    # prompt. The agent may overwrite it on write-back.
    title = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=5, choices=STATUS_CHOICES, default=STATUS_EMPTY)
    # Unguessable write-back handle for the no-MCP fallback (PATCH by URL).
    content_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    summary = models.TextField(blank=True, default='')
    content = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(default=timezone.now)
    populated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Assignment: {self.title or '(untitled)'}"

    @property
    def has_content(self):
        return bool(self.content)

    def save_deliverable(self, title, summary, content):
        """Single write path for both the MCP tool and the PATCH fallback."""
        from activity.services import record_activity, diff
        before = {'title': self.title, 'summary': self.summary, 'status': self.status,
                  'content_chars': len(self.content)}
        if title:
            self.title = title[:255]
        self.summary = summary or ''
        self.content = content
        self.status = self.STATUS_POPULATED
        self.populated_at = timezone.now()
        self.save(update_fields=['title', 'summary', 'content', 'status', 'populated_at'])
        after = {'title': self.title, 'summary': self.summary, 'status': self.status,
                 'content_chars': len(self.content)}
        record_activity('update', 'assignment', self.pk, self.title, diff(before, after))


class AgentConfig(models.Model):
    """Per-user agent settings. Blank template = use the system default."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_config',
    )
    assignment_template = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AgentConfig({self.user})"
