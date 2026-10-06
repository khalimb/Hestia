from django.db.models import Count
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .agent_prompt import DEFAULT_AGENT_PROMPT_TEMPLATE, build_agent_prompt
from .models import McpToken, McpSession, AgentConfig
from .serializers import McpTokenSerializer, McpSessionSerializer, AgentConfigSerializer


def get_or_create_config(user):
    config, _ = AgentConfig.objects.get_or_create(user=user)
    return config


# --- MCP tokens --------------------------------------------------------------

class McpTokenListCreateView(generics.ListCreateAPIView):
    """GET: the current user's tokens (masked). POST {name}: mint one; the
    full token and connector URL are returned ONCE in this response."""
    serializer_class = McpTokenSerializer
    pagination_class = None

    def get_queryset(self):
        return McpToken.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.save(user=request.user)
        data = McpTokenSerializer(token).data
        data['token'] = token.token
        data['connector_url'] = request.build_absolute_uri(f'/mcp/{token.token}/')
        return Response(data, status=status.HTTP_201_CREATED)


class McpTokenDetailView(generics.DestroyAPIView):
    """DELETE: revoke (the connector URL 404s immediately)."""
    serializer_class = McpTokenSerializer

    def get_queryset(self):
        return McpToken.objects.filter(user=self.request.user)


class McpSessionListView(generics.ListAPIView):
    """All agent sessions in the household, newest first, with per-session tool
    call counts and how many logged changes each made. Household-wide on
    purpose: the point is that members can review each other's agents."""
    serializer_class = McpSessionSerializer
    pagination_class = None   # a review list; recent-first and small
    queryset = (McpSession.objects.select_related('token', 'token__user')
                .annotate(activity_count=Count('activity'))
                .order_by('-started_at')[:200])


# --- The agent prompt ----------------------------------------------------------

class AgentPromptView(APIView):
    """The ready-to-paste prompt, rendered with live data from the current
    user's template (or the default)."""

    def get(self, request):
        config = get_or_create_config(request.user)
        template = config.prompt_template or DEFAULT_AGENT_PROMPT_TEMPLATE
        return Response({'prompt': build_agent_prompt(template)})


class AgentConfigView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the current user's prompt template."""
    serializer_class = AgentConfigSerializer

    def get_object(self):
        return get_or_create_config(self.request.user)
