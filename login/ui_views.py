"""Server-rendered pages for the dashboard UI and authentication.

Each dashboard page is a thin shell; the HTML/CSS/JS frontend loads data
from the REST API and renders it client-side.
"""
import os

from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import RegisterForm

PAGES = (
    'dashboard',
    'products',
    'vendors',
    'orders',
    'invoices',
    'alerts',
    'movements',
)

DEFAULT_REGISTRATION_GROUP = os.getenv('DEFAULT_REGISTRATION_GROUP', 'Staff')


@login_required
def page(request, name):
    if name not in PAGES:
        raise Http404
    return render(request, f'login/{name}.html')


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
def register_view(request):
    if request.user.is_authenticated:
        return redirect('ui-dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                user.groups.add(Group.objects.get(name=DEFAULT_REGISTRATION_GROUP))
            except Group.DoesNotExist:
                pass
            auth.login(request, user)
            return redirect('ui-dashboard')
    else:
        form = RegisterForm()

    return render(request, 'login/register.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    auth.logout(request)
    return redirect('login')
