"""Create or update the superuser used to log in to the deployed app.

Credentials come from env vars so the Render deploy can provision an admin
without requiring interactive Shell access.
"""
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update a superuser from ADMIN_USERNAME/ADMIN_PASSWORD/ADMIN_EMAIL.'

    def handle(self, *args, **options):
        username = os.getenv('ADMIN_USERNAME', 'admin')
        password = os.getenv('ADMIN_PASSWORD', 'Hitman@4165')
        email = os.getenv('ADMIN_EMAIL', 'admin@example.com')

        user, created = User.objects.get_or_create(username=username)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f'Superuser ready: {username}'
        ))
