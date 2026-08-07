"""
URL configuration for inventory project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from login import ui_views

urlpatterns = [
    path('', lambda request: redirect('/dashboard/')),
    path('login/', ui_views.login_view, name='login'),
    path('guest/', ui_views.guest_view, name='guest'),
    path('logout/', ui_views.logout_view, name='logout'),
    path('dashboard/', ui_views.page, {'name': 'dashboard'}, name='ui-dashboard'),
    path('products/', ui_views.page, {'name': 'products'}, name='ui-products'),
    path('vendors/', ui_views.page, {'name': 'vendors'}, name='ui-vendors'),
    path('orders/', ui_views.page, {'name': 'orders'}, name='ui-orders'),
    path('invoices/', ui_views.page, {'name': 'invoices'}, name='ui-invoices'),
    path('alerts/', ui_views.page, {'name': 'alerts'}, name='ui-alerts'),
    path('movements/', ui_views.page, {'name': 'movements'}, name='ui-movements'),
    path('admin/', admin.site.urls),
    path('api/', include('login.urls')),
]
