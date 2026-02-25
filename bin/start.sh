#!/usr/bin/env bash
set -euo pipefail

# ── Helper: check whether DATABASE_URL looks like a real connection string ──
db_ready() {
    python -c "
import os, sys
url = os.environ.get('DATABASE_URL', '')
# Unresolved DO template variables or empty string → not ready
if not url or '\${' in url or '://' not in url:
    sys.exit(1)
"
}

if db_ready; then
    echo "==> Ensuring database schema permissions..."
    python << 'PYEOF' || true
import psycopg2, os, urllib.parse

db_url  = os.environ['DATABASE_URL']
parsed  = urllib.parse.urlparse(db_url)
db_user = urllib.parse.unquote(parsed.username or '')

conn = psycopg2.connect(db_url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
    SELECT has_schema_privilege(%s, 'public', 'CREATE')
""", (db_user,))
can_create = cur.fetchone()[0]

if can_create:
    print("User '%s' already has CREATE on public schema – good." % db_user)
else:
    print("User '%s' lacks CREATE on public – attempting fixes..." % db_user)
    try:
        cur.execute('GRANT CREATE ON SCHEMA public TO "%s"' % db_user)
        print("  -> GRANT succeeded.")
    except Exception as e:
        print("  -> GRANT failed: %s" % e)
        conn.rollback()

        schema = db_user.replace('-', '_')
        cur.execute(
            'CREATE SCHEMA IF NOT EXISTS "%s" AUTHORIZATION "%s"'
            % (schema, db_user)
        )
        cur.execute(
            'ALTER ROLE "%s" SET search_path TO "%s", public'
            % (db_user, schema)
        )
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
else
    echo "==> DATABASE_URL not ready (database component may not be attached yet)."
    echo "    Skipping migrations and seeds — the app will start without a DB."
fi

echo "==> Starting gunicorn..."
exec gunicorn hestia_project.wsgi --bind 0.0.0.0:8080 --workers 2
