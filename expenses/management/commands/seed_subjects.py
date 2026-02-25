from django.core.management.base import BaseCommand
from expenses.models import Subject

DEFAULT_SUBJECTS = [
    '42 Oak Street',
    'Toyota Corolla',
]


class Command(BaseCommand):
    help = 'Seed the database with example subjects (can be customised in Settings)'

    def handle(self, *args, **options):
        created_count = 0
        for name in DEFAULT_SUBJECTS:
            _, created = Subject.objects.get_or_create(
                name=name,
                defaults={'is_default': True},
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_count} default subjects '
            f'({len(DEFAULT_SUBJECTS) - created_count} already existed).'
        ))
