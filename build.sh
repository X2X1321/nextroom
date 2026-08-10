#!/bin/bash
set -e

echo "Running collectstatic..."
python manage.py collectstatic --noinput --clear

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating superuser (if env vars are set)..."
python manage.py create_superuser

echo "Build complete!"
