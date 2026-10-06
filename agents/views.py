from django.db.models import Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from activity.services import record_activity

from .assignment_prompt import DEFAULT_ASSIGNMENT_TEMPLATE, build_assignment_prompt
from .models import McpToken, McpSession, Assignment, AgentConfig
from .serializers import (
    McpTokenSerializer, McpSessionSerializer, AssignmentSerializer,
    AssignmentDetailSerializer, AssignmentWritebackSerializer, AgentConfigSerializer,
)


def get_or_create_config(user):
    config, _ = AgentConfig.objects.get_or_create(user=user)
    return config


# --- MCP tokens (owner-facing, JWT) -----------------------------------------

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


# --- Assignments (owner-facing, JWT) ----------------------------------------

class AssignmentListCreateView(generics.ListCreateAPIView):
    """GET: all household assignments. POST {title?}: start one and return it
    with `rendered_prompt`, ready to paste into an agent session."""
    serializer_class = AssignmentSerializer
    pagination_class = None
    queryset = Assignment.objects.select_related('created_by')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save(created_by=request.user)
        record_activity('create', 'assignment', assignment.pk, assignment.title,
                        {'title': {'from': None, 'to': assignment.title}})
        data = AssignmentSerializer(assignment).data
        data['rendered_prompt'] = _render(assignment, request)
        return Response(data, status=status.HTTP_201_CREATED)


class AssignmentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = AssignmentDetailSerializer
    queryset = Assignment.objects.select_related('created_by')

    def perform_destroy(self, instance):
        record_activity('delete', 'assignment', instance.pk, instance.title,
                        {'title': {'from': instance.title, 'to': None},
                         'status': {'from': instance.status, 'to': None}})
        instance.delete()


class AssignmentPromptView(APIView):
    """Re-render the prompt for an existing assignment (resume a session)."""

    def get(self, request, pk):
        assignment = generics.get_object_or_404(Assignment, pk=pk)
        return Response({'prompt': _render(assignment, request)})


def _render(assignment, request):
    config = get_or_create_config(request.user)
    template = config.assignment_template or DEFAULT_ASSIGNMENT_TEMPLATE
    return build_assignment_prompt(template, assignment, request)


class AgentConfigView(generics.RetrieveUpdateAPIView):
    """GET / PATCH the current user's assignment prompt template."""
    serializer_class = AgentConfigSerializer

    def get_object(self):
        return get_or_create_config(self.request.user)


# --- Agent-facing fallback (no MCP) ----------------------------------------

class AssignmentWritebackView(APIView):
    """PATCH by the assignment's unguessable content_token. No bearer token:
    the UUID in the URL is the capability, scoped to this one doc, so the
    rendered prompt carries no reusable secret."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'agent_import'

    def patch(self, request, content_token):
        assignment = Assignment.objects.filter(content_token=content_token).first()
        if assignment is None:
            return Response({'detail': 'Unknown assignment.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssignmentWritebackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment.save_deliverable(
            title=serializer.validated_data.get('title', ''),
            summary=serializer.validated_data.get('summary', ''),
            content=serializer.validated_data['content'],
        )
        return Response(AssignmentSerializer(assignment).data)
