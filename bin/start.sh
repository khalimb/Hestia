#!/usr/bin/env bash
set -euo pipefail

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Seeding default data..."
python manage.py seed_expense_types || true
python manage.py seed_subjects || true

echo "==> Starting gunicorn..."
exec gunicorn hestia_project.wsgi --bind 0.0.0.0:8080 --workers 2
