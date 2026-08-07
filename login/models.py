from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.crypto import get_random_string


class Vendor(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    vendor = models.ForeignKey(Vendor, related_name='products', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.check_low_stock()

    def check_low_stock(self):
        """Automated low-stock detection with alert creation and Celery notification."""
        if self.stock_quantity <= self.reorder_level:
            alert, created = StockAlert.objects.get_or_create(
                product=self,
                resolved=False,
                defaults={
                    'message': f'{self.name} is below reorder level '
                               f'({self.stock_quantity}/{self.reorder_level}).',
                },
            )
            if created:
                try:
                    from login.tasks import inventory_low_stock_notification
                    inventory_low_stock_notification.delay(
                        self.name, self.stock_quantity
                    )
                except Exception:
                    # Celery broker may not be running in dev; log but don't crash
                    pass
        else:
            # Stock replenished — resolve any open alerts
            StockAlert.objects.filter(
                product=self, resolved=False
            ).update(resolved=True)

    def adjust_stock(self, quantity, notes=''):
        """Adjust stock by a signed quantity and record the movement.

        Positive values add stock, negative values remove it. Stock is never
        allowed to go below zero.
        """
        previous = self.stock_quantity
        self.stock_quantity = max(0, previous + quantity)
        self.save(update_fields=['stock_quantity', 'updated_at'])
        StockMovement.objects.create(
            product=self,
            movement_type=(
                StockMovement.MovementType.STOCK_IN
                if quantity >= 0
                else StockMovement.MovementType.STOCK_OUT
            ),
            reference_type=StockMovement.ReferenceType.ADJUSTMENT,
            reference_id='',
            quantity=abs(quantity),
            previous_quantity=previous,
            new_quantity=self.stock_quantity,
            notes=notes,
        )
        self.check_low_stock()
        return self


class Order(models.Model):
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    vendor = models.ForeignKey(
        Vendor, related_name='orders', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processed', 'Processed'),
            ('shipped', 'Shipped'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
    )
    stock_restored = models.BooleanField(
        default=False, editable=False,
        help_text='Tracks whether order line items have had their stock returned.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = get_random_string(length=12).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.customer_name}"

    def recalculate_total(self):
        """Recalculate the order total from its line items and refresh the invoice."""
        self.total_amount = sum(
            (item.quantity * item.unit_price for item in self.items.all()),
            Decimal('0.00'),
        )
        self.save(update_fields=['total_amount', 'updated_at'])
        self.generate_invoice()

    def cancel(self):
        """Cancel the order and return all reserved stock to inventory."""
        if self.status == 'cancelled':
            return
        if self.status == 'shipped':
            raise ValidationError('A shipped order cannot be cancelled.')
        if not self.stock_restored:
            for item in self.items.all():
                item.restore_stock()
            self.stock_restored = True
        self.status = 'cancelled'
        self.save(update_fields=['status', 'stock_restored', 'updated_at'])

    def transition_to(self, new_status):
        """Move the order through the allowed status workflow."""
        allowed_transitions = {
            'pending': {'processed', 'cancelled'},
            'processed': {'shipped', 'cancelled'},
            'shipped': set(),
            'cancelled': set(),
        }
        if new_status not in allowed_transitions.get(self.status, set()):
            raise ValidationError(
                f'Cannot transition order from "{self.status}" to "{new_status}".'
            )
        if new_status == 'cancelled':
            self.cancel()
        else:
            self.status = new_status
            self.save(update_fields=['status', 'updated_at'])

    def generate_invoice(self):
        """Create or update the invoice linked to this order."""
        invoice, created = Invoice.objects.get_or_create(
            order=self,
            defaults={
                'invoice_number': get_random_string(length=12).upper(),
                'customer_name': self.customer_name,
                'customer_email': self.customer_email,
                'total_amount': self.total_amount,
            },
        )
        if not created:
            invoice.total_amount = self.total_amount
            invoice.save(update_fields=['total_amount'])
        return invoice


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(
        Product, related_name='order_items', on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('order', 'product')

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def _stock_movement_notes(self, action):
        order_ref = self.order.order_number or str(self.order.id or 'draft')
        return f'{action} - {order_ref}'

    def _apply_stock_change(self, quantity):
        """Deduct `quantity` from the product, guarding against overselling."""
        product = self.product
        if product.stock_quantity < quantity:
            raise ValidationError(
                f'Insufficient stock for {product.name}: available '
                f'{product.stock_quantity}, requested {quantity}.'
            )
        previous = product.stock_quantity
        product.stock_quantity -= quantity
        product.save(update_fields=['stock_quantity', 'updated_at'])
        StockMovement.objects.create(
            product=product,
            movement_type=StockMovement.MovementType.STOCK_OUT,
            reference_type=StockMovement.ReferenceType.SALE,
            reference_id=self.order.order_number or '',
            quantity=quantity,
            previous_quantity=previous,
            new_quantity=product.stock_quantity,
            notes=self._stock_movement_notes('Sale'),
        )

    def _restore_stock(self, quantity):
        """Return `quantity` units to the product inventory."""
        product = self.product
        previous = product.stock_quantity
        product.stock_quantity += quantity
        product.save(update_fields=['stock_quantity', 'updated_at'])
        StockMovement.objects.create(
            product=product,
            movement_type=StockMovement.MovementType.STOCK_IN,
            reference_type=StockMovement.ReferenceType.RETURN,
            reference_id=self.order.order_number or '',
            quantity=quantity,
            previous_quantity=previous,
            new_quantity=product.stock_quantity,
            notes=self._stock_movement_notes('Return'),
        )

    def restore_stock(self):
        """Public helper to return this item's full quantity to stock."""
        self._restore_stock(self.quantity)

    def save(self, *args, **kwargs):
        if self.unit_price is None or self.unit_price <= 0:
            self.unit_price = self.product.price

        if self._state.adding:
            self._apply_stock_change(self.quantity)
        else:
            previous_quantity = (
                OrderItem.objects.filter(pk=self.pk)
                .values_list('quantity', flat=True)
                .first()
                or 0
            )
            delta = self.quantity - previous_quantity
            if delta > 0:
                self._apply_stock_change(delta)
            elif delta < 0:
                self._restore_stock(-delta)

        super().save(*args, **kwargs)
        self.order.recalculate_total()

    def delete(self, *args, **kwargs):
        order = self.order
        if not order.stock_restored:
            self.restore_stock()
        result = super().delete(*args, **kwargs)
        order.recalculate_total()
        return result


class Invoice(models.Model):
    order = models.OneToOneField(
        Order, related_name='invoice', on_delete=models.CASCADE,
    )
    invoice_number = models.CharField(max_length=20, unique=True, editable=False)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = get_random_string(length=12).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.customer_name}"


class StockAlert(models.Model):
    product = models.ForeignKey(
        Product, related_name='alerts', on_delete=models.CASCADE,
    )
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.product.name} alert"


class StockMovement(models.Model):
    """Audit trail for every stock change across the inventory."""

    class MovementType(models.TextChoices):
        STOCK_IN = 'IN', 'Stock In'
        STOCK_OUT = 'OUT', 'Stock Out'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'

    class ReferenceType(models.TextChoices):
        SALE = 'SALE', 'Sale Order'
        RETURN = 'RETURN', 'Order Return'
        ADJUSTMENT = 'ADJUSTMENT', 'Manual Adjustment'
        INITIAL = 'INITIAL', 'Initial Stock'

    product = models.ForeignKey(
        Product, related_name='stock_movements', on_delete=models.CASCADE,
    )
    movement_type = models.CharField(
        max_length=20, choices=MovementType.choices,
    )
    reference_type = models.CharField(
        max_length=20, choices=ReferenceType.choices,
        default=ReferenceType.ADJUSTMENT,
    )
    reference_id = models.CharField(max_length=50, blank=True)
    quantity = models.PositiveIntegerField()
    previous_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]

    def __str__(self):
        return f'{self.product.sku} {self.get_movement_type_display()} {self.quantity}'
