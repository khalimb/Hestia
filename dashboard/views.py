from datetime import timedelta
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from expenses.models import Expense, Occurrence


class DashboardSummaryView(APIView):
    def get(self, request):
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        if today.month == 12:
            last_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        month_occurrences = Occurrence.objects.filter(
            due_date__gte=first_of_month,
            due_date__lte=last_of_month,
        )

        currency_totals = month_occurrences.values('currency').annotate(
            total=Sum('expected_amount'), count=Count('id'),
        ).order_by('currency')

        type_breakdown = month_occurrences.values(
            'expense__expense_type__name',
        ).annotate(
            total=Sum('expected_amount'), count=Count('id'),
        ).order_by('-total')

        overdue_count = Occurrence.objects.filter(
            due_date__lt=today, status__in=['pending', 'overdue'],
        ).count()

        due_today_count = Occurrence.objects.filter(
            due_date=today, status='pending',
        ).count()

        return Response({
            'month': today.strftime('%B %Y'),
            'currency_totals': list(currency_totals),
            'type_breakdown': list(type_breakdown),
            'overdue_count': overdue_count,
            'due_today_count': due_today_count,
        })


class DashboardUpcomingView(APIView):
    def get(self, request):
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        occurrences = Occurrence.objects.filter(
            due_date__gte=today, due_date__lte=thirty_days,
            status__in=['pending', 'overdue'],
        ).select_related('expense', 'expense__subject').order_by('due_date')

        data = []
        for occ in occurrences:
            data.append({
                'id': str(occ.id),
                'expense_name': occ.expense.name,
                'expense_id': str(occ.expense.id),
                'subject_name': occ.expense.subject.name if occ.expense.subject else None,
                'due_date': occ.due_date.isoformat(),
                'expected_amount': str(occ.expected_amount),
                'currency': occ.currency,
                'status': occ.status,
            })
        return Response(data)


class DashboardOverdueView(APIView):
    def get(self, request):
        today = timezone.now().date()
        occurrences = Occurrence.objects.filter(
            due_date__lt=today, status__in=['pending', 'overdue'],
        ).select_related('expense', 'expense__subject').order_by('due_date')

        data = []
        for occ in occurrences:
            data.append({
                'id': str(occ.id),
                'expense_name': occ.expense.name,
                'expense_id': str(occ.expense.id),
                'subject_name': occ.expense.subject.name if occ.expense.subject else None,
                'due_date': occ.due_date.isoformat(),
                'expected_amount': str(occ.expected_amount),
                'currency': occ.currency,
                'status': occ.status,
                'days_overdue': (today - occ.due_date).days,
            })
        return Response(data)
