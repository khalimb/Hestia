from django.urls import path
from . import import_views

urlpatterns = [
    # Owner-facing (JWT auth, used by the Settings UI)
    path('config/', import_views.ImportConfigView.as_view(), name='agent-import-config'),
    path('token/', import_views.ImportTokenView.as_view(), name='agent-import-token'),
    path('prompt/', import_views.ImportPromptView.as_view(), name='agent-import-prompt'),
    # Agent-facing (scoped import-token auth)
    path('expenses/', import_views.ImportExpenseCreateView.as_view(), name='agent-import-expense-create'),
    path('options/', import_views.ImportOptionsView.as_view(), name='agent-import-options'),
]
