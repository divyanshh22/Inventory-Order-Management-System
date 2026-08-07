"""Create demo user accounts so visitors can log in and explore the app."""
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create demo accounts: admin, staff, and vendor.'

    def handle(self, *args, **options):
        groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in ('Admins', 'Staff', 'Vendors')
        }

        demo_users = [
            ('admin', 'Admin@123', True, ['Admins']),
            ('staff', 'Staff@123', False, ['Staff']),
            ('vendor', 'Vendor@123', False, ['Vendors']),
        ]

        for username, password, is_superuser, group_names in demo_users:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.is_superuser = is_superuser
            user.is_staff = is_superuser
            user.is_active = True
            user.email = f'{username}@example.com'
            user.save()
            user.groups.set([groups[name] for name in group_names])
            self.stdout.write(self.style.SUCCESS(
                f'Demo user ready: {username} (password: {password})'
            ))
