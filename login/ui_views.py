"""Server-rendered pages for the dashboard UI.

Each page is a thin shell; the HTML/CSS/JS frontend loads data from the
REST API and renders it client-side.
"""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

PAGES = (
    'dashboard',
    'products',
    'vendors',
    'orders',
    'invoices',
    'alerts',
    'movements',
)


@login_required
def page(request, name):
    if name not in PAGES:
        raise Http404
    return render(request, f'login/{name}.html')
