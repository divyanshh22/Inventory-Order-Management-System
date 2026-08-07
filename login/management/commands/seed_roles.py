"""Create the role groups used for role-based access control."""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

ROLES = ('Admins', 'Managers', 'Staff', 'Vendors')


class Command(BaseCommand):
    help = 'Seed the RBAC role groups (Admins, Managers, Staff, Vendors).'

    def handle(self, *args, **options):
        for role in ROLES:
            group, created = Group.objects.get_or_create(name=role)
            self.stdout.write(
                self.style.SUCCESS(f'{"Created" if created else "Already exists"} group: {role}')
            )
