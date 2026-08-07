from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    InvoiceDownloadView,
    InvoiceListView,
    OrderCancelView,
    OrderListCreateView,
    OrderProcessView,
    OrderRetrieveUpdateDestroyView,
    OrderShipView,
    ProductListCreateView,
    ProductRetrieveUpdateDestroyView,
    RegisterView,
    ReportSummaryView,
    StockAlertListView,
    StockAlertResolveView,
    StockMovementListView,
    TopProductsReportView,
    VendorListCreateView,
    VendorReportView,
    VendorRetrieveUpdateDestroyView,
)

urlpatterns = [
    # Authentication
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', obtain_auth_token, name='auth-login'),

    # Vendors
    path('vendors/', VendorListCreateView.as_view(), name='vendor-list-create'),
    path('vendors/<int:pk>/', VendorRetrieveUpdateDestroyView.as_view(), name='vendor-detail'),

    # Products
    path('products/', ProductListCreateView.as_view(), name='product-list-create'),
    path('products/<int:pk>/', ProductRetrieveUpdateDestroyView.as_view(), name='product-detail'),

    # Orders
    path('orders/', OrderListCreateView.as_view(), name='order-list-create'),
    path('orders/<int:pk>/', OrderRetrieveUpdateDestroyView.as_view(), name='order-detail'),
    path('orders/<int:pk>/process/', OrderProcessView.as_view(), name='order-process'),
    path('orders/<int:pk>/ship/', OrderShipView.as_view(), name='order-ship'),
    path('orders/<int:pk>/cancel/', OrderCancelView.as_view(), name='order-cancel'),

    # Invoices
    path('invoices/', InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/<int:pk>/download/', InvoiceDownloadView.as_view(), name='invoice-download'),

    # Stock Alerts
    path('alerts/', StockAlertListView.as_view(), name='alert-list'),
    path('alerts/<int:pk>/resolve/', StockAlertResolveView.as_view(), name='alert-resolve'),

    # Stock Movements (audit trail)
    path('stock-movements/', StockMovementListView.as_view(), name='stock-movement-list'),
    path(
        'products/<int:product_id>/stock-movements/',
        StockMovementListView.as_view(),
        name='product-stock-movement-list',
    ),

    # Reports
    path('reports/summary/', ReportSummaryView.as_view(), name='report-summary'),
    path('reports/top-products/', TopProductsReportView.as_view(), name='report-top-products'),
    path('reports/vendors/', VendorReportView.as_view(), name='report-vendors'),
]
