from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Order


@receiver(pre_delete, sender=Order)
def restore_stock_on_order_delete(sender, instance, **kwargs):
    """Return stock to inventory when an order is hard-deleted.

    Runs before the cascade deletes the order items, so each item can still
    be queried. Orders that were already cancelled have their stock returned
    via ``Order.cancel`` and are skipped to avoid double-restoring.
    """
    if instance.stock_restored:
        return
    for item in instance.items.select_related('product'):
        item.restore_stock()
