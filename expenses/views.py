from django.utils import timezone
from rest_framework import viewsets, generics, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Subject, ExpenseType, Expense, Occurrence
from .serializers import (
    SubjectSerializer, ExpenseTypeSerializer, ExpenseSerializer,
    ExpenseDetailSerializer, OccurrenceSerializer,
)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        subject = self.get_object()
        if subject.is_default:
            return Response(
                {'detail': 'Default subjects cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if subject.expenses.exists():
            return Response(
                {'detail': 'Cannot delete subject with existing expenses.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class ExpenseTypeViewSet(viewsets.ModelViewSet):
    queryset = ExpenseType.objects.all()
    serializer_class = ExpenseTypeSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        expense_type = self.get_object()
        if expense_type.is_default:
            return Response(
                {'detail': 'Default expense types cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if expense_type.expenses.exists():
            return Response(
                {'detail': 'Cannot delete expense type with existing expenses.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related('subject', 'expense_type').all()
    filterset_fields = ['subject', 'expense_type', 'is_active', 'currency', 'recurrence_type']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'amount', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExpenseDetailSerializer
        return ExpenseSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class OccurrenceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Occurrence.objects.select_related('expense').all()
    serializer_class = OccurrenceSerializer
    filterset_fields = ['status', 'expense', 'currency']
    ordering_fields = ['due_date', 'expected_amount']

    def get_queryset(self):
        qs = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(due_date__gte=date_from)
        if date_to:
            qs = qs.filter(due_date__lte=date_to)
        return qs

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        today = timezone.now().date()
        thirty_days = today + timezone.timedelta(days=30)
        occs = self.get_queryset().filter(
            due_date__gte=today, due_date__lte=thirty_days,
            status__in=['pending', 'overdue'],
        )
        serializer = self.get_serializer(occs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        today = timezone.now().date()
        occs = self.get_queryset().filter(
            due_date__lt=today, status__in=['pending', 'overdue'],
        )
        serializer = self.get_serializer(occs, many=True)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_status = request.data.get('status')
        if new_status and new_status in dict(Occurrence.STATUS_CHOICES):
            instance.status = new_status
            instance.save()
            return Response(self.get_serializer(instance).data)
        return Response(
            {'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST,
        )
