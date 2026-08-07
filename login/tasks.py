"""
Celery tasks for automated inventory management.

Includes:
- Periodic low-stock scanning (runs every 30 minutes via Celery Beat)
- Individual low-stock notification dispatch
- Email summary for admin
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def inventory_low_stock_notification(self, product_name, stock_quantity):
    """Send an individual low-stock notification (triggered from Product.check_low_stock)."""
    try:
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@inventorysystem.com')
        send_mail(
            subject=f'[Low Stock] {product_name} - Only {stock_quantity} left',
            message=(
                f'Product "{product_name}" is running low.\n'
                f'Current stock: {stock_quantity} units.\n\n'
                f'Please reorder soon to avoid stockouts.'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@inventorysystem.com'),
            recipient_list=[admin_email],
            fail_silently=True,
        )
        logger.info('Low-stock notification sent for %s (%d units)', product_name, stock_quantity)
    except Exception as exc:
        logger.error('Failed to send low-stock email for %s: %s', product_name, exc)
        raise self.retry(exc=exc, countdown=60)

    return {
        'product': product_name,
        'stock_quantity': stock_quantity,
        'message': f'{product_name} is running low at {stock_quantity} units.',
    }


@shared_task
def check_all_low_stock():
    """Periodic task: scan ALL products for low stock and create alerts.

    Scheduled via CELERY_BEAT_SCHEDULE (every 30 minutes).
    """
    from login.models import Product

    low_stock_products = Product.objects.filter(stock_quantity__lte=F('reorder_level'))
    alerts_created = 0
    low_items = []

    for product in low_stock_products:
        product.check_low_stock()
        low_items.append(
            f'{product.name} (SKU: {product.sku}): '
            f'{product.stock_quantity}/{product.reorder_level}'
        )
        alerts_created += 1

    # Send summary email to admin
    if low_items:
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@inventorysystem.com')
        body = (
            'The following products are below their reorder level:\n\n'
            + '\n'.join(f'  - {item}' for item in low_items)
            + f'\n\nTotal: {alerts_created} product(s) need attention.'
        )
        try:
            send_mail(
                subject=f'[Inventory] Low Stock Summary \u2013 {alerts_created} product(s)',
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@inventorysystem.com'),
                recipient_list=[admin_email],
                fail_silently=True,
            )
        except Exception as exc:
            logger.error('Failed to send low-stock summary email: %s', exc)

    total_products = Product.objects.count()
    logger.info('Low-stock scan complete. %d/%d product(s) flagged.', alerts_created, total_products)
    return {
        'scanned': total_products,
        'low_stock_count': alerts_created,
        'products': low_items,
    }
