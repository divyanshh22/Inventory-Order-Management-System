#!/usr/bin/env bash
# Install dependencies, collect static files, and apply migrations on Render.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_roles
python manage.py seed_demo_data
python manage.py ensure_admin
