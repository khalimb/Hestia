from django.core.management.base import BaseCommand
from expenses.models import ExpenseType

DEFAULT_EXPENSE_TYPES = [
    'Rent',
    'Water',
    'Electricity',
    'Gas',
    'Internet',
    'Tax',
    'Other',
]


class Command(BaseCommand):
    help = 'Seed the database with default expense types'

    def handle(self, *args, **options):
        created_count = 0
        for type_name in DEFAULT_EXPENSE_TYPES:
            _, created = ExpenseType.objects.get_or_create(
                name=type_name,
                defaults={'is_default': True},
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_count} default expense types '
            f'({len(DEFAULT_EXPENSE_TYPES) - created_count} already existed).'
        ))
