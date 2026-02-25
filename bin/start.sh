#!/usr/bin/env bash
set -euo pipefail

echo "==> Ensuring database schema permissions..."
python << 'PYEOF'
import psycopg2, os, urllib.parse

db_url  = os.environ['DATABASE_URL']
parsed  = urllib.parse.urlparse(db_url)
db_user = urllib.parse.unquote(parsed.username or '')

conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

# Check if the user can already create in 'public'
cur.execute("""
    SELECT has_schema_privilege(%s, 'public', 'CREATE')
""", (db_user,))
can_create = cur.fetchone()[0]

if can_create:
    print("User '%s' already has CREATE on public schema – good." % db_user)
else:
    print("User '%s' lacks CREATE on public – attempting fixes..." % db_user)

    # Attempt 1: GRANT directly (works if user owns the database)
    try:
        cur.execute('GRANT CREATE ON SCHEMA public TO "%s"' % db_user)
        print("  -> GRANT succeeded.")
    except Exception as e:
        print("  -> GRANT failed: %s" % e)
        conn.rollback()

        # Attempt 2: create a user-owned schema and adjust search_path
        schema = db_user.replace('-', '_')
        cur.execute(
            'CREATE SCHEMA IF NOT EXISTS "%s" AUTHORIZATION "%s"'
            % (schema, db_user)
        )
        cur.execute(
            'ALTER ROLE "%s" SET search_path TO "%s", public'
            % (db_user, schema)
        )
        # Apply to the current session too
        cur.execute('SET search_path TO "%s", public' % schema)
        print("  -> Created schema '%s' and set search_path." % schema)

conn.close()
PYEOF

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Seeding default data..."
python manage.py seed_expense_types || true
python manage.py seed_categories   || true
python manage.py seed_subjects     || true

echo "==> Starting gunicorn..."
exec gunicorn hestia_project.wsgi --bind 0.0.0.0:8080 --workers 2
