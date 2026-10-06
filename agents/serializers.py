from rest_framework import serializers

from .agent_prompt import DEFAULT_AGENT_PROMPT_TEMPLATE, TEMPLATE_VARIABLES
from .models import McpToken, McpSession, AgentConfig


class McpTokenSerializer(serializers.ModelSerializer):
    """List view of a token: never the full value after creation."""
    token_masked = serializers.CharField(read_only=True)

    class Meta:
        model = McpToken
        fields = ['id', 'name', 'token_masked', 'active', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'token_masked', 'active', 'created_at', 'last_used_at']


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


class AgentConfigSerializer(serializers.ModelSerializer):
    """Reads return the effective template (custom or default); a blank or
    unchanged-default submission stores empty so default updates keep
    flowing through."""
    prompt_template = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False,
    )
    is_custom_template = serializers.SerializerMethodField()
    default_template = serializers.SerializerMethodField()
    template_variables = serializers.SerializerMethodField()

    class Meta:
        model = AgentConfig
        fields = ['prompt_template', 'is_custom_template', 'default_template',
                  'template_variables', 'updated_at']
        read_only_fields = ['updated_at']

    def get_is_custom_template(self, obj):
        return bool(obj.prompt_template)

    def get_default_template(self, obj):
        return DEFAULT_AGENT_PROMPT_TEMPLATE

    def get_template_variables(self, obj):
        return TEMPLATE_VARIABLES

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not instance.prompt_template:
            data['prompt_template'] = DEFAULT_AGENT_PROMPT_TEMPLATE
        return data

    def update(self, instance, validated_data):
        if 'prompt_template' in validated_data:
            template = validated_data['prompt_template']
            if template.strip() in ('', DEFAULT_AGENT_PROMPT_TEMPLATE.strip()):
                instance.prompt_template = ''
            else:
                instance.prompt_template = template
            instance.save(update_fields=['prompt_template', 'updated_at'])
        return instance
