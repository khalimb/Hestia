from django.urls import path
from . import views

urlpatterns = [
    # Owner-facing (JWT)
    path('mcp-tokens/', views.McpTokenListCreateView.as_view(), name='agents-mcp-tokens'),
    path('mcp-tokens/<uuid:pk>/', views.McpTokenDetailView.as_view(), name='agents-mcp-token'),
    path('mcp-sessions/', views.McpSessionListView.as_view(), name='agents-mcp-sessions'),
    path('assignments/', views.AssignmentListCreateView.as_view(), name='agents-assignments'),
    path('assignments/<uuid:pk>/', views.AssignmentDetailView.as_view(), name='agents-assignment'),
    path('assignments/<uuid:pk>/prompt/', views.AssignmentPromptView.as_view(),
         name='agents-assignment-prompt'),
    path('config/', views.AgentConfigView.as_view(), name='agents-config'),
    # Agent-facing fallback (capability URL, no auth header)
    path('assignments/by-token/<uuid:content_token>/', views.AssignmentWritebackView.as_view(),
         name='agents-assignment-writeback'),
]
