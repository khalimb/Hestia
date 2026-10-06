from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.filters import OrderingFilter

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityListView(generics.ListAPIView):
    """Paginated change log, newest first. Filters: actor, source, token,
    session, entity_type, entity_id, action, plus date_from / date_to."""
    serializer_class = ActivityLogSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['actor', 'source', 'token', 'session', 'entity_type', 'entity_id', 'action']
    ordering_fields = ['created_at']

    def get_queryset(self):
        qs = ActivityLog.objects.select_related('actor', 'token')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs
