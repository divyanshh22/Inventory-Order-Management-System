"""Server-rendered pages for the dashboard UI and authentication.

Each dashboard page is a thin shell; the HTML/CSS/JS frontend loads data
from the REST API and renders it client-side.
"""
import os

from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .permissions import MANAGEMENT_GROUPS

PAGES = (
    'dashboard',
    'products',
    'vendors',
    'orders',
    'invoices',
    'alerts',
    'movements',
)

GUEST_USERNAME = os.getenv('GUEST_USERNAME', 'guest')


def _can_write(user):
    """Staff/management users can mutate data; everyone else is read-only."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=MANAGEMENT_GROUPS).exists()


@login_required
def page(request, name):
    if name not in PAGES:
        raise Http404
    return render(request, f'login/{name}.html', {
        'can_write': _can_write(request.user),
    })


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('ui-dashboard')

    error = None
    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = auth.authenticate(request, username=username, password=password)
        if user is not None:
            auth.login(request, user)
            next_url = request.POST.get('next') or next_url
            if next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect('ui-dashboard')
        error = 'Invalid username or password.'

    return render(request, 'login/login.html', {'error': error, 'next': next_url})


@require_http_methods(['GET', 'POST'])
def guest_view(request):
    """Log in as a shared read-only guest user."""
    if request.user.is_authenticated:
        return redirect('ui-dashboard')

    guest, created = User.objects.get_or_create(username=GUEST_USERNAME)
    if created:
        guest.set_unusable_password()
        guest.is_active = True
        guest.email = 'guest@example.com'
        try:
            guest.groups.add(Group.objects.get(name='Staff'))
        except Group.DoesNotExist:
            pass
        guest.save()

    auth.login(request, guest)
    return redirect('ui-dashboard')


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    auth.logout(request)
    return redirect('login')
