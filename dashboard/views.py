from datetime import timedelta
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from expenses.models import Subject, ExpenseType, Expense, Occurrence
from expenses.services import ensure_occurrences_generated
from transactions.models import Transaction
from .analytics import spend_summary, parse_window


class DashboardSummaryView(APIView):
    def get(self, request):
        ensure_occurrences_generated()
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

        # One-off spending this month, and a combined per-type view so the
        # category chart reflects recurring + variable together.
        month_transactions = Transaction.objects.filter(
            date__gte=first_of_month, date__lte=last_of_month,
        )
        transaction_totals = month_transactions.values('currency').annotate(
            total=Sum('amount'), count=Count('id'),
        ).order_by('currency')
        transaction_types = month_transactions.values(
            'expense_type__name',
        ).annotate(total=Sum('amount'), count=Count('id'))

        combined = {}
        for row in type_breakdown:
            name = row['expense__expense_type__name']
            combined.setdefault(name, {'name': name, 'recurring': 0, 'one_off': 0})
            combined[name]['recurring'] = row['total']
        for row in transaction_types:
            name = row['expense_type__name']
            combined.setdefault(name, {'name': name, 'recurring': 0, 'one_off': 0})
            combined[name]['one_off'] = row['total']
        combined_breakdown = sorted(
            ({**c, 'total': c['recurring'] + c['one_off']} for c in combined.values()),
            key=lambda c: -c['total'],
        )

        return Response({
            'month': today.strftime('%B %Y'),
            'currency_totals': list(currency_totals),
            'type_breakdown': list(type_breakdown),
            'transaction_currency_totals': list(transaction_totals),
            'combined_type_breakdown': combined_breakdown,
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
        ).select_related(
            'expense', 'expense__subject', 'expense__payment_method',
            'expense__account', 'expense__responsible',
        ).order_by('due_date')

        data = []
        for occ in occurrences:
            data.append({
                'id': str(occ.id),
                'expense_name': occ.expense.name,
                'expense_id': str(occ.expense.id),
                'subject_name': occ.expense.subject.name if occ.expense.subject else None,
                'payment_method_name': (
                    occ.expense.payment_method.name if occ.expense.payment_method else None
                ),
                'account_name': occ.expense.account.name if occ.expense.account else None,
                'responsible_name': (
                    occ.expense.responsible.display_name if occ.expense.responsible else None
                ),
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
        ).select_related(
            'expense', 'expense__subject', 'expense__payment_method',
            'expense__account', 'expense__responsible',
        ).order_by('due_date')

        data = []
        for occ in occurrences:
            data.append({
                'id': str(occ.id),
                'expense_name': occ.expense.name,
                'expense_id': str(occ.expense.id),
                'subject_name': occ.expense.subject.name if occ.expense.subject else None,
                'payment_method_name': (
                    occ.expense.payment_method.name if occ.expense.payment_method else None
                ),
                'account_name': occ.expense.account.name if occ.expense.account else None,
                'responsible_name': (
                    occ.expense.responsible.display_name if occ.expense.responsible else None
                ),
                'due_date': occ.due_date.isoformat(),
                'expected_amount': str(occ.expected_amount),
                'currency': occ.currency,
                'status': occ.status,
                'days_overdue': (today - occ.due_date).days,
            })
        return Response(data)


class DashboardCoverageView(APIView):
    """Coverage matrix of subjects × expense types.

    Reports, for every (subject, expense_type) pair, how many active expenses
    link them. A zero/absent cell is a gap — a combination for which no
    expense has been added yet — so admins can spot what's still missing.
    """

    def get(self, request):
        subjects = list(Subject.objects.order_by('name').values('id', 'name'))
        expense_types = list(
            ExpenseType.objects.order_by('name').values('id', 'name')
        )

        active_expenses = Expense.objects.filter(is_active=True)

        # One grouped query: count of active expenses per (subject, type) pair.
        pair_counts = active_expenses.values(
            'subject_id', 'expense_type_id',
        ).annotate(count=Count('id'))

        # matrix[subject_id][expense_type_id] = count (string keys for JSON).
        matrix = {}
        no_subject = 0
        no_type = 0
        for row in pair_counts:
            sid, tid, count = row['subject_id'], row['expense_type_id'], row['count']
            # Expenses missing a subject or type can't be placed in a cell;
            # surface them separately rather than dropping them silently.
            if sid is None:
                no_subject += count
            if tid is None:
                no_type += count
            if sid is None or tid is None:
                continue
            matrix.setdefault(str(sid), {})[str(tid)] = count

        return Response({
            'subjects': [
                {'id': str(s['id']), 'name': s['name']} for s in subjects
            ],
            'expense_types': [
                {'id': str(t['id']), 'name': t['name']} for t in expense_types
            ],
            'matrix': matrix,
            'unassigned': {'no_subject': no_subject, 'no_type': no_type},
            'total_active_expenses': active_expenses.count(),
        })


class DashboardAnalyticsView(APIView):
    """Spend over an arbitrary window (default: this month). Query params
    date_from / date_to as YYYY-MM-DD. See dashboard/analytics.py."""

    def get(self, request):
        try:
            start, end = parse_window(request.query_params.get('date_from'),
                                      request.query_params.get('date_to'))
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        if (end - start).days > 366 * 3:
            return Response({'detail': 'window must be 3 years or less'}, status=400)
        ensure_occurrences_generated()
        normalise = request.query_params.get('normalise', '').upper() or None
        if normalise not in (None, 'USD'):
            return Response({'detail': 'normalise supports USD only'}, status=400)
        return Response(spend_summary(start, end, normalise_to=normalise))
