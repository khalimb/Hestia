from django.db.models import Q
from rest_framework import viewsets

from activity.services import delete_logged

from .models import Transaction
from .serializers import TransactionSerializer


class TransactionViewSet(viewsets.ModelViewSet):
    """One-off spending. Filters: the dictionary ids, paid_by, currency, plus
    date_from / date_to and a merchant/notes search."""
    queryset = Transaction.objects.select_related(
        'expense_type', 'subject', 'payment_method', 'account', 'paid_by',
    )
    serializer_class = TransactionSerializer
    filterset_fields = ['expense_type', 'subject', 'payment_method', 'account', 'paid_by', 'currency']
    ordering_fields = ['date', 'amount', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get('date_from'):
            qs = qs.filter(date__gte=params['date_from'])
        if params.get('date_to'):
            qs = qs.filter(date__lte=params['date_to'])
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(merchant__icontains=search) | Q(notes__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        delete_logged(TransactionSerializer, instance)
