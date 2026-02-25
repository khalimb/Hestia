#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Installing Node.js for frontend build..."
NODE_VERSION="22.14.0"
curl -sL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" | tar -xJ
export PATH="$(pwd)/node-v${NODE_VERSION}-linux-x64/bin:$PATH"
echo "    Node $(node --version) / npm $(npm --version)"

echo "==> Installing frontend dependencies..."
cd frontend
npm ci
echo "==> Building frontend..."
npm run build
cd ..

echo "==> Copying index.html to Django templates..."
mkdir -p templates
cp frontend/dist/index.html templates/index.html

echo "==> Collecting static files..."
# Unset DATABASE_URL so Django falls back to SQLite (no PG needed at build time)
DATABASE_URL="" python manage.py collectstatic --noinput

echo "==> Build complete (migrations run at startup)."
