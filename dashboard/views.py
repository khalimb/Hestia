from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.views import APIView
from expenses.models import Subject, ExpenseType, Expense, Occurrence
from expenses.services import ensure_occurrences_generated
from transactions.models import Transaction
from activity.services import record_activity

from .analytics import spend_summary, breakdown_items, parse_window, GROUPS
from .models import CoverageMark


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
    """Coverage grid, one section per subject type.

    Each section lists that type's subjects against the categories marked as
    applicable to the type, counting active expenses per (subject, category).
    A zero cell is a gap. Expenses on a subject in a category outside its
    type's list are counted separately as `outside`, so nothing is hidden.
    Untyped subjects form a final section against every category.
    """

    def get(self, request):
        from expenses.models import SubjectType
        active = Expense.objects.filter(is_active=True)
        pair_counts = {}
        no_subject = no_type = 0
        for row in active.values('subject_id', 'expense_type_id').annotate(count=Count('id')):
            sid, tid, count = row['subject_id'], row['expense_type_id'], row['count']
            if sid is None:
                no_subject += count
            if tid is None:
                no_type += count
            if sid is None or tid is None:
                continue
            pair_counts.setdefault(sid, {})[tid] = count

        all_types = list(ExpenseType.objects.order_by('name').values('id', 'name'))
        by_id = {t['id']: t for t in all_types}
        # Manual marks on empty cells: subject -> {type: status}.
        marks = {}
        for m in CoverageMark.objects.values('subject_id', 'expense_type_id', 'status'):
            marks.setdefault(m['subject_id'], {})[m['expense_type_id']] = m['status']

        def section(subject_type, subjects, type_ids):
            columns = [by_id[t] for t in type_ids if t in by_id] if type_ids is not None else all_types
            column_ids = {c['id'] for c in columns}
            matrix, outside, section_marks = {}, {}, {}
            for subj in subjects:
                counts = pair_counts.get(subj['id'], {})
                matrix[str(subj['id'])] = {str(t): n for t, n in counts.items() if t in column_ids}
                extra = {by_id[t]['name']: n for t, n in counts.items() if t not in column_ids and t in by_id}
                if extra:
                    outside[str(subj['id'])] = extra
                # A mark only matters where no active expense exists.
                cell_marks = {str(t): st for t, st in marks.get(subj['id'], {}).items()
                              if t in column_ids and not counts.get(t)}
                if cell_marks:
                    section_marks[str(subj['id'])] = cell_marks
            return {
                'subject_type': subject_type,
                'subjects': [{'id': str(x['id']), 'name': x['name']} for x in subjects],
                'expense_types': [{'id': str(c['id']), 'name': c['name']} for c in columns],
                'matrix': matrix,
                # subject id -> {category name: count} for expenses outside the type's categories
                'outside': outside,
                # subject id -> {type id: 'in_progress' | 'not_needed'} on empty cells
                'marks': section_marks,
            }

        sections = []
        for st in SubjectType.objects.prefetch_related('expense_types').order_by('name'):
            subjects = list(st.subjects.filter(is_active=True).order_by('name').values('id', 'name'))
            if not subjects:
                continue   # a type nobody uses yet has nothing to cover
            type_ids = [t.id for t in st.expense_types.all()]
            sections.append(section({'id': str(st.id), 'name': st.name}, subjects, sorted(
                type_ids, key=lambda t: by_id[t]['name'] if t in by_id else '')))
        untyped = list(Subject.objects.filter(subject_type__isnull=True, is_active=True)
                       .order_by('name').values('id', 'name'))
        if untyped:
            sections.append(section(None, untyped, None))

        return Response({
            'sections': sections,
            'unassigned': {'no_subject': no_subject, 'no_type': no_type},
            'total_active_expenses': active.count(),
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


class DashboardBreakdownItemsView(APIView):
    """Drill-down for one by_category / by_subject cell of the analytics: the
    occurrences and transactions behind it. group = category | subject;
    id = the dictionary id, or "none" for unassigned."""

    def get(self, request):
        try:
            start, end = parse_window(request.query_params.get('date_from'),
                                      request.query_params.get('date_to'))
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)
        group = request.query_params.get('group', '').strip().lower()
        if group not in GROUPS:
            return Response({'detail': f'group must be one of {list(GROUPS)}'}, status=400)
        raw = request.query_params.get('id', '').strip()
        if not raw:
            return Response({'detail': 'id is required (a dictionary id or "none")'}, status=400)
        group_id = None if raw.lower() == 'none' else raw
        model = ExpenseType if group == 'category' else Subject
        if group_id is not None:
            try:
                exists = model.objects.filter(pk=group_id).exists()
            except (ValueError, ValidationError):
                exists = False
            if not exists:
                return Response({'detail': f'unknown {group} id'}, status=404)
        currency = request.query_params.get('currency', '').upper() or None
        normalise = request.query_params.get('normalise', '').upper() or None
        return Response(breakdown_items(start, end, group, group_id, currency, normalise_to=normalise))


class DashboardCoverageMarkView(APIView):
    """POST {subject, expense_type, status}: set a mark on an empty coverage
    cell ('in_progress' | 'not_needed'), or clear it with status null."""

    def post(self, request):
        subject = generics.get_object_or_404(Subject, pk=request.data.get('subject'))
        expense_type = generics.get_object_or_404(ExpenseType, pk=request.data.get('expense_type'))
        status_value = request.data.get('status') or None
        if status_value not in (None, CoverageMark.IN_PROGRESS, CoverageMark.NOT_NEEDED):
            return Response({'detail': 'status must be in_progress, not_needed or null'}, status=400)
        label = f'{subject.name} × {expense_type.name}'
        existing = CoverageMark.objects.filter(subject=subject, expense_type=expense_type).first()
        before = existing.status if existing else None
        if status_value is None:
            if existing:
                mark_id = existing.pk          # delete() clears the pk
                existing.delete()
                record_activity('delete', 'coverage_mark', mark_id, label,
                                {'status': {'from': before, 'to': None}})
            return Response({'subject': str(subject.id), 'expense_type': str(expense_type.id), 'status': None})
        mark, created = CoverageMark.objects.update_or_create(
            subject=subject, expense_type=expense_type,
            defaults={'status': status_value, 'updated_by': request.user})
        if before != status_value:
            record_activity('create' if created else 'update', 'coverage_mark', mark.pk, label,
                            {'status': {'from': before, 'to': status_value}})
        return Response({'subject': str(subject.id), 'expense_type': str(expense_type.id),
                         'status': mark.status})
