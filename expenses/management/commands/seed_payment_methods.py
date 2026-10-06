from django.core.management.base import BaseCommand
from expenses.models import PaymentMethod

# (name, requires_account). Methods that draw from a specific account let an
# expense also record which PaymentAccount it is paid from.
DEFAULT_PAYMENT_METHODS = [
    ('Cash', False),
    ('Card', True),
    ('Direct Debit', True),
    ('Standing Order', True),
    ('Bank Transfer', True),
]


class Command(BaseCommand):
    help = 'Seed the database with default payment methods'

    def handle(self, *args, **options):
        created_count = 0
        for name, requires_account in DEFAULT_PAYMENT_METHODS:
            _, created = PaymentMethod.objects.get_or_create(
                name=name,
                defaults={'is_default': True, 'requires_account': requires_account},
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_count} default payment methods '
            f'({len(DEFAULT_PAYMENT_METHODS) - created_count} already existed).'
        ))
