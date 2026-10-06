from django.urls import path
from . import views

urlpatterns = [
    path('mcp-tokens/', views.McpTokenListCreateView.as_view(), name='agents-mcp-tokens'),
    path('mcp-tokens/<uuid:pk>/', views.McpTokenDetailView.as_view(), name='agents-mcp-token'),
    path('mcp-sessions/', views.McpSessionListView.as_view(), name='agents-mcp-sessions'),
    path('prompt/', views.AgentPromptView.as_view(), name='agents-prompt'),
    path('config/', views.AgentConfigView.as_view(), name='agents-config'),
]
