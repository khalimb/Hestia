from django.db.models import Sum
from rest_framework import generics, status
from rest_framework.response import Response
from expenses.models import Occurrence
from .models import Payment
from .serializers import PaymentSerializer


class OccurrencePaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(occurrence_id=self.kwargs['occurrence_id'])

    def perform_create(self, serializer):
        occurrence = Occurrence.objects.get(pk=self.kwargs['occurrence_id'])
        payment = serializer.save(
            logged_by=self.request.user,
            occurrence=occurrence,
        )
        self._update_occurrence_status(occurrence)
        return payment

    def _update_occurrence_status(self, occurrence):
        total_paid = occurrence.payments.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        if total_paid >= occurrence.expected_amount:
            occurrence.status = 'paid'
        elif total_paid > 0:
            occurrence.status = 'partial'
        occurrence.save()


class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def perform_update(self, serializer):
        payment = serializer.save()
        self._update_occurrence_status(payment.occurrence)

    def perform_destroy(self, instance):
        occurrence = instance.occurrence
        instance.delete()
        self._update_occurrence_status(occurrence)

    def _update_occurrence_status(self, occurrence):
        from django.utils import timezone
        total_paid = occurrence.payments.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        if total_paid >= occurrence.expected_amount:
            occurrence.status = 'paid'
        elif total_paid > 0:
            occurrence.status = 'partial'
        elif occurrence.due_date < timezone.now().date():
            occurrence.status = 'overdue'
        else:
            occurrence.status = 'pending'
        occurrence.save()
