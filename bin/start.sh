#!/usr/bin/env bash
set -euo pipefail

echo "==> Granting schema permissions..."
python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
conn.autocommit = True
cur = conn.cursor()
cur.execute('SELECT current_user')
user = cur.fetchone()[0]
cur.execute('GRANT ALL ON SCHEMA public TO \"%s\"' % user)
print('Granted schema permissions to', user)
conn.close()
" || true

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Seeding default data..."
python manage.py seed_expense_types || true
python manage.py seed_subjects || true

echo "==> Starting gunicorn..."
exec gunicorn hestia_project.wsgi --bind 0.0.0.0:8080 --workers 2
