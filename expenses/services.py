import threading
import time
from django.core.management import call_command

# Simple in-memory throttle: track last run timestamp
_lock = threading.Lock()
_last_run = 0.0
# Minimum seconds between runs (1 hour)
_COOLDOWN = 3600


def ensure_occurrences_generated():
    """Run generate_occurrences if it hasn't been run recently.

    Safe to call on every request — uses a 1-hour cooldown so the actual
    command only executes at most once per hour regardless of traffic.
    """
    global _last_run
    now = time.monotonic()

    with _lock:
        if now - _last_run < _COOLDOWN:
            return
        _last_run = now

    # Run outside the lock so we don't block other requests
    call_command('generate_occurrences')
