from django.core.management.base import BaseCommand
from expenses.models import SubjectType, Subject, ExpenseType

# (type name, categories that apply, default subjects of that type)
DEFAULT_SUBJECT_TYPES = [
    ('Property', ['Rent', 'Water', 'Electricity', 'Gas', 'Internet', 'Tax'], ['42 Oak Street']),
    ('Vehicle', ['Tax'], ['Toyota Corolla']),
    ('Person', [], []),
]


class Command(BaseCommand):
    help = 'Seed default subject types with their applicable categories (customise in Settings)'

    def handle(self, *args, **options):
        created_count = 0
        for name, category_names, subject_names in DEFAULT_SUBJECT_TYPES:
            subject_type, created = SubjectType.objects.get_or_create(
                name=name, defaults={'is_default': True},
            )
            if created:
                created_count += 1
                # Categories only on first creation, so later edits in Settings stick.
                subject_type.expense_types.set(ExpenseType.objects.filter(name__in=category_names))
            # Seeded example subjects get their type if nobody has typed them yet.
            Subject.objects.filter(name__in=subject_names, subject_type__isnull=True).update(
                subject_type=subject_type)
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_count} default subject types '
            f'({len(DEFAULT_SUBJECT_TYPES) - created_count} already existed).'
        ))
