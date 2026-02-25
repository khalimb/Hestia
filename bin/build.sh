#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Installing Node.js for frontend build..."
NODE_VERSION="20.11.1"
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
python manage.py collectstatic --noinput

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Seeding default data..."
python manage.py seed_expense_types
python manage.py seed_subjects

echo "==> Build complete."
