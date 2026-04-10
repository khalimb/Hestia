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
from .services import ensure_occurrences_generated, force_generate_occurrences


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

    def list(self, request, *args, **kwargs):
        ensure_occurrences_generated()
        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExpenseDetailSerializer
        return ExpenseSerializer

    @action(detail=False, methods=['post'])
    def generate_occurrences(self, request):
        """Manually trigger occurrence generation with diagnostics."""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        from django.utils import timezone as tz

        today = tz.now().date()
        horizon = today + timedelta(days=90)

        active_expenses = Expense.objects.filter(is_active=True)
        expense_info = []
        for exp in active_expenses:
            # Reproduce the date logic inline to diagnose
            effective_start = max(exp.start_date, today - timedelta(days=30))
            effective_end = exp.end_date if exp.end_date and exp.end_date < horizon else horizon

            step_map = {
                'weekly': relativedelta(weeks=1),
                'monthly': relativedelta(months=1),
                'quarterly': relativedelta(months=3),
                'biannual': relativedelta(months=6),
                'annual': relativedelta(years=1),
                'biennial': relativedelta(years=2),
            }
            step = step_map.get(exp.recurrence_type)

            # Walk forward and collect dates
            dates = []
            current = exp.start_date
            iterations = 0
            while current <= effective_end and iterations < 10000:
                if current >= effective_start:
                    dates.append(str(current))
                next_date = current + step
                if exp.recurrence_type != 'weekly':
                    from calendar import monthrange
                    _, max_day = monthrange(next_date.year, next_date.month)
                    next_date = next_date.replace(day=min(exp.start_date.day, max_day))
                current = next_date
                iterations += 1

            expense_info.append({
                'name': exp.name,
                'recurrence_type': exp.recurrence_type,
                'start_date': str(exp.start_date),
                'end_date': str(exp.end_date) if exp.end_date else None,
                'today': str(today),
                'effective_start': str(effective_start),
                'effective_end': str(effective_end),
                'step': str(step),
                'dates_generated': dates,
                'iterations': iterations,
            })

        try:
            force_generate_occurrences()
            error_msg = None
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()

        total = Occurrence.objects.count()
        pending = Occurrence.objects.filter(status='pending', due_date__gte=today).count()

        return Response({
            'active_expenses': len(expense_info),
            'expenses': expense_info,
            'total_occurrences': total,
            'pending_upcoming': pending,
            'error': error_msg,
        })

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
