"""Inventory reporting queries for dashboard summaries and analytics."""
from django.db.models import Count, F, Q, Sum

from .models import Order, OrderItem, Product, Vendor


def inventory_summary():
    """High-level inventory and order metrics for the dashboard."""
    product_stats = Product.objects.aggregate(
        total_products=Count('id'),
        total_stock=Sum('stock_quantity'),
        stock_value=Sum(F('stock_quantity') * F('price')),
        low_stock=Count('id', filter=Q(stock_quantity__lte=F('reorder_level'))),
        out_of_stock=Count('id', filter=Q(stock_quantity=0)),
    )
    order_stats = Order.objects.aggregate(
        total_orders=Count('id'),
        revenue=Sum('total_amount', filter=~Q(status='cancelled')),
        pending=Count('id', filter=Q(status='pending')),
        processed=Count('id', filter=Q(status='processed')),
        shipped=Count('id', filter=Q(status='shipped')),
        cancelled=Count('id', filter=Q(status='cancelled')),
    )
    return {
        'products': {
            'total': product_stats['total_products'] or 0,
            'total_stock_units': product_stats['total_stock'] or 0,
            'stock_value': product_stats['stock_value'] or 0,
            'low_stock': product_stats['low_stock'] or 0,
            'out_of_stock': product_stats['out_of_stock'] or 0,
        },
        'orders': {
            'total': order_stats['total_orders'] or 0,
            'revenue': order_stats['revenue'] or 0,
            'by_status': {
                'pending': order_stats['pending'] or 0,
                'processed': order_stats['processed'] or 0,
                'shipped': order_stats['shipped'] or 0,
                'cancelled': order_stats['cancelled'] or 0,
            },
        },
    }


def top_products(limit=10):
    """Best-selling products ranked by total quantity ordered."""
    return list(
        OrderItem.objects.values(
            'product__id', 'product__name', 'product__sku',
        )
        .annotate(
            units_sold=Sum('quantity'),
            revenue=Sum(F('quantity') * F('unit_price')),
        )
        .order_by('-units_sold')[:limit]
    )


def vendor_report():
    """Per-vendor product, order, and revenue breakdown."""
    vendors = Vendor.objects.annotate(
        product_count=Count('products'),
        order_count=Count('orders'),
    )
    rows = []
    for vendor in vendors:
        revenue = Order.objects.filter(
            vendor=vendor,
        ).exclude(status='cancelled').aggregate(total=Sum('total_amount'))
        rows.append({
            'id': vendor.id,
            'name': vendor.name,
            'products': vendor.product_count,
            'orders': vendor.order_count,
            'revenue': revenue['total'] or 0,
        })
    return rows
