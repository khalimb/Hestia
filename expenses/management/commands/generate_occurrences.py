from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from expenses.models import Expense, Occurrence


class Command(BaseCommand):
    help = 'Generate upcoming occurrences for all active expenses (90-day lookahead)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='Number of days to look ahead (default: 90)',
        )

    def handle(self, *args, **options):
        lookahead_days = options['days']
        today = timezone.now().date()
        horizon = today + timedelta(days=lookahead_days)

        expenses = Expense.objects.filter(is_active=True)
        created_count = 0
        overdue_count = 0

        for expense in expenses:
            dates = self._get_occurrence_dates(expense, today, horizon)
            for d in dates:
                _, created = Occurrence.objects.get_or_create(
                    expense=expense,
                    due_date=d,
                    defaults={
                        'expected_amount': expense.amount,
                        'currency': expense.currency,
                        'status': 'overdue' if d < today else 'pending',
                    },
                )
                if created:
                    created_count += 1

        # Mark overdue occurrences
        overdue_count = Occurrence.objects.filter(
            due_date__lt=today, status='pending',
        ).update(status='overdue')

        self.stdout.write(self.style.SUCCESS(
            f'Generated {created_count} new occurrences. '
            f'Marked {overdue_count} as overdue.'
        ))

    def _get_occurrence_dates(self, expense, start, end):
        dates = []
        if expense.start_date > end:
            return dates

        effective_start = max(expense.start_date, start - timedelta(days=30))
        effective_end = expense.end_date if expense.end_date and expense.end_date < end else end

        if expense.recurrence_type == 'weekly':
            current = effective_start
            # Align to the correct day of week
            days_ahead = expense.recurrence_day - current.weekday()
            if days_ahead < 0:
                days_ahead += 7
            current = current + timedelta(days=days_ahead)
            while current <= effective_end:
                if current >= expense.start_date:
                    dates.append(current)
                current += timedelta(weeks=1)

        elif expense.recurrence_type == 'monthly':
            current = effective_start.replace(day=1)
            while current <= effective_end:
                try:
                    occ_date = current.replace(day=min(expense.recurrence_day, self._days_in_month(current)))
                except ValueError:
                    occ_date = current.replace(day=self._days_in_month(current))
                if expense.start_date <= occ_date <= effective_end:
                    dates.append(occ_date)
                current += relativedelta(months=1)

        elif expense.recurrence_type == 'quarterly':
            current = effective_start.replace(day=1)
            while current <= effective_end:
                if expense.recurrence_month and current.month == expense.recurrence_month:
                    pass  # This is a quarter start month
                quarter_months = self._get_quarter_months(expense.recurrence_month or 1)
                if current.month in quarter_months:
                    try:
                        occ_date = current.replace(
                            day=min(expense.recurrence_day, self._days_in_month(current))
                        )
                    except ValueError:
                        occ_date = current.replace(day=self._days_in_month(current))
                    if expense.start_date <= occ_date <= effective_end:
                        dates.append(occ_date)
                current += relativedelta(months=1)

        elif expense.recurrence_type == 'annual':
            current_year = effective_start.year
            while current_year <= effective_end.year:
                month = expense.recurrence_month or 1
                try:
                    occ_date = date(
                        current_year, month,
                        min(expense.recurrence_day, self._days_in_month(date(current_year, month, 1)))
                    )
                except ValueError:
                    current_year += 1
                    continue
                if expense.start_date <= occ_date <= effective_end:
                    dates.append(occ_date)
                current_year += 1

        return dates

    def _days_in_month(self, d):
        if d.month == 12:
            return 31
        next_month = d.replace(month=d.month + 1, day=1)
        return (next_month - timedelta(days=1)).day

    def _get_quarter_months(self, start_month):
        return [
            start_month,
            ((start_month - 1 + 3) % 12) + 1,
            ((start_month - 1 + 6) % 12) + 1,
            ((start_month - 1 + 9) % 12) + 1,
        ]
