from django.core.management.base import BaseCommand
from expenses.models import Category

DEFAULT_CATEGORIES = [
    {'name': 'Housing', 'icon': 'pi pi-home', 'colour': '#6366f1'},
    {'name': 'Utilities', 'icon': 'pi pi-bolt', 'colour': '#f59e0b'},
    {'name': 'Insurance', 'icon': 'pi pi-shield', 'colour': '#10b981'},
    {'name': 'Subscriptions', 'icon': 'pi pi-play', 'colour': '#ec4899'},
    {'name': 'Transport', 'icon': 'pi pi-car', 'colour': '#3b82f6'},
    {'name': 'Childcare & Education', 'icon': 'pi pi-graduation-cap', 'colour': '#8b5cf6'},
    {'name': 'Financial', 'icon': 'pi pi-wallet', 'colour': '#ef4444'},
    {'name': 'Other', 'icon': 'pi pi-ellipsis-h', 'colour': '#6b7280'},
]


class Command(BaseCommand):
    help = 'Seed the database with default expense categories'

    def handle(self, *args, **options):
        created_count = 0
        for cat_data in DEFAULT_CATEGORIES:
            _, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'is_default': True,
                    'icon': cat_data['icon'],
                    'colour': cat_data['colour'],
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_count} default categories '
            f'({len(DEFAULT_CATEGORIES) - created_count} already existed).'
        ))
