from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from django.utils import timezone

from core.authentication import ImportTokenAuthentication
from expenses.models import Subject, ExpenseType, Expense
from expenses.serializers import SubjectSerializer, ExpenseTypeSerializer, ExpenseSerializer
from .models import AgentImportConfig, generate_import_token
from .import_serializers import AgentImportConfigSerializer
from .import_prompt import build_prompt, DEFAULT_PROMPT_TEMPLATE


def get_or_create_config(user):
    config, _ = AgentImportConfig.objects.get_or_create(user=user)
    return config


# --- Owner-facing endpoints (default JWT auth; managed from Settings) ---------

class ImportConfigView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the current user's import config (prompt template + status)."""
    serializer_class = AgentImportConfigSerializer

    def get_object(self):
        return get_or_create_config(self.request.user)


class ImportTokenView(APIView):
    """Generate/rotate (POST) or revoke (DELETE) the scoped submission token."""

    def post(self, request):
        config = get_or_create_config(request.user)
        config.token = generate_import_token()
        config.token_created_at = timezone.now()
        config.save(update_fields=['token', 'token_created_at', 'updated_at'])
        # Returned in full here; afterwards it's only ever embedded in the prompt.
        return Response(
            {'token': config.token, 'token_created_at': config.token_created_at},
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        config = get_or_create_config(request.user)
        config.token = None
        config.token_created_at = None
        config.save(update_fields=['token', 'token_created_at', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImportPromptView(APIView):
    """Assemble the full, ready-to-paste prompt (template + live data + token)."""

    def get(self, request):
        config = get_or_create_config(request.user)
        if not config.has_token:
            return Response(
                {'detail': 'Generate an import token before exporting the prompt.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        template = config.prompt_template or DEFAULT_PROMPT_TEMPLATE
        prompt = build_prompt(template, request, config)
        return Response({
            'prompt': prompt,
            'endpoint': request.build_absolute_uri(
                '/api/v1/agent-import/expenses/',
            ),
        })


# --- Agent-facing endpoints (scoped import-token auth; called by the agent) ---

class ImportExpenseCreateView(generics.CreateAPIView):
    """Create an Expense from an agent submission, authed by the import token."""
    authentication_classes = [ImportTokenAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'agent_import'
    serializer_class = ExpenseSerializer

    def perform_create(self, serializer):
        # request.user is the token's owner, resolved by ImportTokenAuthentication.
        serializer.save(created_by=self.request.user)


class ImportOptionsView(APIView):
    """Let the agent fetch the latest subjects / expense types / recurrence types."""
    authentication_classes = [ImportTokenAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'agent_import'

    def get(self, request):
        return Response({
            'subjects': SubjectSerializer(
                Subject.objects.order_by('name'), many=True,
            ).data,
            'expense_types': ExpenseTypeSerializer(
                ExpenseType.objects.order_by('name'), many=True,
            ).data,
            'recurrence_types': [value for value, _ in Expense.RECURRENCE_CHOICES],
        })
