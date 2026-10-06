from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.display_name', read_only=True, default=None)
    via = serializers.CharField(read_only=True)
    token_name = serializers.CharField(source='token.name', read_only=True, default=None)

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'created_at', 'actor', 'actor_name', 'source', 'via', 'token', 'token_name',
            'session', 'action', 'entity_type', 'entity_id', 'entity_label', 'changes',
        ]
        read_only_fields = fields
