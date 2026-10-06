from rest_framework import serializers

from .assignment_prompt import DEFAULT_ASSIGNMENT_TEMPLATE, TEMPLATE_VARIABLES
from .models import McpToken, McpSession, Assignment, AgentConfig


class McpTokenSerializer(serializers.ModelSerializer):
    """List view of a token: never the full value after creation."""
    token_masked = serializers.CharField(read_only=True)

    class Meta:
        model = McpToken
        fields = ['id', 'name', 'token_masked', 'active', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'token_masked', 'active', 'created_at', 'last_used_at']


class AssignmentSerializer(serializers.ModelSerializer):
    has_content = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.display_name', read_only=True)

    class Meta:
        model = Assignment
        fields = [
            'id', 'title', 'status', 'summary', 'has_content',
            'created_by', 'created_by_name', 'started_at', 'populated_at',
        ]
        read_only_fields = [
            'id', 'status', 'summary', 'has_content', 'created_by',
            'created_by_name', 'started_at', 'populated_at',
        ]


class AssignmentDetailSerializer(AssignmentSerializer):
    class Meta(AssignmentSerializer.Meta):
        fields = AssignmentSerializer.Meta.fields + ['content']
        read_only_fields = AssignmentSerializer.Meta.read_only_fields + ['content']


class AssignmentWritebackSerializer(serializers.Serializer):
    """Body of the no-MCP fallback PATCH (and the shape assignment_save takes)."""
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    summary = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField(trim_whitespace=False)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('content must not be empty.')
        return value


class AgentConfigSerializer(serializers.ModelSerializer):
    """Same contract as the agent-import config: reads return the effective
    template (custom or default); blank or unchanged-default submissions
    store empty so default updates keep flowing through."""
    assignment_template = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False,
    )
    is_custom_template = serializers.SerializerMethodField()
    default_template = serializers.SerializerMethodField()
    template_variables = serializers.SerializerMethodField()

    class Meta:
        model = AgentConfig
        fields = ['assignment_template', 'is_custom_template', 'default_template',
                  'template_variables', 'updated_at']
        read_only_fields = ['updated_at']

    def get_is_custom_template(self, obj):
        return bool(obj.assignment_template)

    def get_default_template(self, obj):
        return DEFAULT_ASSIGNMENT_TEMPLATE

    def get_template_variables(self, obj):
        return TEMPLATE_VARIABLES

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.assignment_template:
            data['assignment_template'] = DEFAULT_ASSIGNMENT_TEMPLATE
        return data

    def update(self, instance, validated_data):
        if 'assignment_template' in validated_data:
            template = validated_data['assignment_template']
            if template.strip() in ('', DEFAULT_ASSIGNMENT_TEMPLATE.strip()):
                instance.assignment_template = ''
            else:
                instance.assignment_template = template
            instance.save(update_fields=['assignment_template', 'updated_at'])
        return instance


class McpSessionSerializer(serializers.ModelSerializer):
    """One agent session: which client, whose token, what it called, how many
    changes it made (activity rows link back by session)."""
    token_name = serializers.CharField(source='token.name', read_only=True)
    user = serializers.UUIDField(source='token.user_id', read_only=True)
    user_name = serializers.CharField(source='token.user.display_name', read_only=True)
    activity_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = McpSession
        fields = [
            'id', 'token', 'token_name', 'user', 'user_name', 'client_name', 'client_version',
            'protocol_version', 'started_at', 'last_seen_at', 'ended_at', 'request_count',
            'tool_calls', 'activity_count',
        ]
        read_only_fields = fields
