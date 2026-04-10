import os
import threading
import time
from django.apps import AppConfig


class ExpensesConfig(AppConfig):
    name = 'expenses'

    def ready(self):
        # Only start the scheduler in the main gunicorn process, not during
        # manage.py commands or the reloader's child process.
        if os.environ.get('RUN_MAIN') or os.environ.get('DJANGO_SETTINGS_MODULE') is None:
            return
        # Guard against running in management commands (migrate, collectstatic, etc.)
        import sys
        if len(sys.argv) > 1 and sys.argv[1] != 'runserver':
            # In production (gunicorn), sys.argv[1] won't be a management command name
            if sys.argv[0].endswith('manage.py'):
                return
        _start_occurrence_scheduler()


def _start_occurrence_scheduler():
    """Run generate_occurrences once daily in a background daemon thread."""
    def loop():
        from django.core.management import call_command
        # Wait 60s after startup before first run to let migrations finish
        time.sleep(60)
        while True:
            try:
                call_command('generate_occurrences')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f'Occurrence generation failed: {e}')
            # Sleep 24 hours
            time.sleep(86400)

    t = threading.Thread(target=loop, daemon=True, name='occurrence-scheduler')
    t.start()
