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
        """Generate occurrence dates by stepping forward from start_date."""
        dates = []
        if expense.start_date > end:
            return dates

        effective_end = expense.end_date if expense.end_date and expense.end_date < end else end

        # Determine the step interval based on recurrence type
        step = self._get_step(expense.recurrence_type)

        # Walk forward from start_date in fixed steps until we pass effective_end.
        # We collect all dates from start_date onward — get_or_create in the
        # caller handles duplicates, and the horizon bounds the upper end.
        current = expense.start_date
        while current <= effective_end:
            dates.append(current)
            current = self._advance(current, expense, step)

        return dates

    def _get_step(self, recurrence_type):
        """Return the relativedelta step for a recurrence type."""
        return {
            'weekly': relativedelta(weeks=1),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'biannual': relativedelta(months=6),
            'annual': relativedelta(years=1),
            'biennial': relativedelta(years=2),
        }[recurrence_type]

    def _advance(self, current, expense, step):
        """Advance the date by one step, clamping day to the start_date's day."""
        next_date = current + step
        # For month/year-based recurrences, pin to the original day of month
        # (e.g. start_date Jan 31 + 1 month -> Feb 28, then Mar 31)
        if expense.recurrence_type != 'weekly':
            target_day = expense.start_date.day
            max_day = self._days_in_month(next_date)
            next_date = next_date.replace(day=min(target_day, max_day))
        return next_date

    def _days_in_month(self, d):
        if d.month == 12:
            return 31
        next_month = d.replace(month=d.month + 1, day=1)
        return (next_month - timedelta(days=1)).day
