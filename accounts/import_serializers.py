from rest_framework import serializers

from .models import AgentImportConfig
from .import_prompt import DEFAULT_PROMPT_TEMPLATE, TEMPLATE_VARIABLES


class AgentImportConfigSerializer(serializers.ModelSerializer):
    """Settings-facing view of a user's import config.

    `prompt_template` is the only writable field. When the user hasn't
    customised it, reads return the system default so the UI can show and edit
    it; an empty submission resets back to the default.
    """
    prompt_template = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False,
    )
    has_token = serializers.BooleanField(read_only=True)
    token_masked = serializers.CharField(read_only=True)
    is_custom_template = serializers.SerializerMethodField()
    default_template = serializers.SerializerMethodField()
    template_variables = serializers.SerializerMethodField()

    class Meta:
        model = AgentImportConfig
        fields = [
            'prompt_template', 'has_token', 'token_masked',
            'is_custom_template', 'default_template', 'template_variables',
            'token_created_at', 'last_used_at',
        ]
        read_only_fields = ['token_created_at', 'last_used_at']

    def get_is_custom_template(self, obj):
        return bool(obj.prompt_template)

    def get_default_template(self, obj):
        return DEFAULT_PROMPT_TEMPLATE

    def get_template_variables(self, obj):
        return TEMPLATE_VARIABLES

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Surface the effective template (custom or default) for display/editing.
        if not instance.prompt_template:
            data['prompt_template'] = DEFAULT_PROMPT_TEMPLATE
        return data

    def update(self, instance, validated_data):
        if 'prompt_template' in validated_data:
            template = validated_data['prompt_template']
            # Blank, or an unchanged copy of the default, means "use the default":
            # store empty so future default changes flow through automatically.
            if template.strip() in ('', DEFAULT_PROMPT_TEMPLATE.strip()):
                instance.prompt_template = ''
            else:
                instance.prompt_template = template
            instance.save(update_fields=['prompt_template', 'updated_at'])
        return instance
