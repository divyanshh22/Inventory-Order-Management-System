"""Role-based access control for the inventory API.

Roles map to Django Groups (seeded via ``python manage.py seed_roles``):
    - Admins  -> full management access
    - Managers -> full management access
    - Staff   -> read access to sensitive data
    - Vendors -> authenticated vendors
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

MANAGEMENT_GROUPS = ('Admins', 'Managers')


def user_in_groups(user, groups):
    return (
        user is not None
        and user.is_authenticated
        and user.groups.filter(name__in=groups).exists()
    )


class IsStaffRole(BasePermission):
    """Allow access to superusers, staff users, Admins, and Managers."""

    message = 'Staff or management privileges are required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        return user_in_groups(user, MANAGEMENT_GROUPS)


class IsVendorRole(BasePermission):
    """Allow access to users in the Vendors group."""

    message = 'Vendor privileges are required.'

    def has_permission(self, request, view):
        return user_in_groups(request.user, ('Vendors',))


class IsStaffOrReadOnly(BasePermission):
    """Allow safe methods to anyone; writes require staff/management role."""

    message = 'Staff or management privileges are required to write.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsStaffRole().has_permission(request, view)
