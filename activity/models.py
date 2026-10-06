"""Activity log: one row per change, with who made it, through which door
(web UI, agent import, MCP client + session), and a before/after diff.

Rows are written by `activity.services.record_activity`, called from the
shared serializers (so the web API and the MCP tools log identically) and
from the few delete paths. Never edited; deleting an actor leaves the row.
"""
import uuid

from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    SOURCE_WEB = 'web'
    SOURCE_MCP = 'mcp'
    SOURCE_IMPORT = 'import'
    SOURCE_SYSTEM = 'system'
    SOURCE_CHOICES = [
        (SOURCE_WEB, 'Web'),
        (SOURCE_MCP, 'MCP agent'),
        (SOURCE_IMPORT, 'Agent import'),
        (SOURCE_SYSTEM, 'System'),
    ]
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activity',
    )
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_WEB)
    # Which MCP client (token) and which of its sessions, when source is mcp.
    token = models.ForeignKey(
        'agents.McpToken', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activity',
    )
    session = models.ForeignKey(
        'agents.McpSession', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='activity',
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    # 'expense' | 'subject' | 'expense_type' | 'payment_method' | 'payment_account'
    # | 'payment' | 'assignment'. Free text so new entities need no migration.
    entity_type = models.CharField(max_length=30, db_index=True)
    entity_id = models.UUIDField(db_index=True)
    # Snapshot of the entity's name at the time, so deleted entities still read.
    entity_label = models.CharField(max_length=255, blank=True, default='')
    # {field: {"from": x, "to": y}}. Create: from=None; delete: to=None.
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['entity_type', 'entity_id'])]

    def __str__(self):
        return f"{self.action} {self.entity_type} {self.entity_label} by {self.actor}"

    @property
    def via(self):
        """Human label for the door the change came through."""
        if self.source == self.SOURCE_MCP:
            return f"MCP · {self.token.name}" if self.token else 'MCP'
        return dict(self.SOURCE_CHOICES).get(self.source, self.source)
