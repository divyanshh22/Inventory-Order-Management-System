"""Seed the database with demo data so the UI is populated.

Creates vendors, products (including low/out-of-stock items that trigger
alerts), and orders which automatically generate invoices, deduct stock,
and record stock movements.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from login.models import Order, OrderItem, Product, StockAlert, Vendor


class Command(BaseCommand):
    help = 'Seed the database with demo vendors, products, and orders.'

    def handle(self, *args, **options):
        if Vendor.objects.exists():
            self.stdout.write(self.style.WARNING(
                'Demo data already exists (vendors found). Skipping.'
            ))
            return

        with transaction.atomic():
            self._seed()

        orders = Order.objects.count()
        products_count = Product.objects.count()
        open_alerts = StockAlert.objects.filter(resolved=False).count()
        revenue = sum(
            o.total_amount for o in Order.objects.exclude(status='cancelled')
        )

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully:'))
        self.stdout.write(f'  Vendors : 3')
        self.stdout.write(f'  Products: {products_count}')
        self.stdout.write(f'  Orders  : {orders} (revenue INR {revenue:,.2f})')
        self.stdout.write(f'  Open low-stock alerts: {open_alerts}')

    def _seed(self):
        vendors = [
            Vendor.objects.create(
                name='TechNova Supplies',
                contact_person='Rahul Sharma',
                email='rahul@technova.com',
                phone='+91 98765 43210',
            ),
            Vendor.objects.create(
                name='Global Traders',
                contact_person='Priya Patel',
                email='priya@globaltraders.com',
                phone='+91 91234 56780',
            ),
            Vendor.objects.create(
                name='Fresh Grocers Co.',
                contact_person='Arun Verma',
                email='arun@freshgrocers.com',
                phone='+91 90000 12345',
            ),
        ]

        # (sku, name, description, price, stock, reorder_level, vendor)
        product_specs = [
            ('TECH-001', 'Wireless Mouse', 'Ergonomic wireless mouse', '499.00', 45, 10, 0),
            ('TECH-002', 'Mechanical Keyboard', 'RGB mechanical keyboard', '2499.00', 12, 5, 0),
            ('TECH-003', '27" Monitor', 'Full HD IPS monitor', '12999.00', 3, 5, 0),
            ('TECH-004', 'USB-C Hub', '7-in-1 USB-C hub', '1299.00', 60, 15, 0),
            ('GLOB-001', 'Stainless Flask', '750ml insulated flask', '899.00', 8, 10, 1),
            ('GLOB-002', 'Leather Wallet', 'Slim leather wallet', '1499.00', 30, 8, 1),
            ('GLOB-003', 'Travel Backpack', 'Waterproof backpack', '2999.00', 0, 5, 1),
            ('FRESH-001', 'Basmati Rice 5kg', 'Premium basmati rice', '649.00', 120, 30, 2),
            ('FRESH-002', 'Cold Pressed Oil 1L', 'Pure cold pressed oil', '349.00', 15, 20, 2),
            ('FRESH-003', 'Organic Honey 500g', 'Raw organic honey', '425.00', 25, 10, 2),
        ]

        products = []
        for sku, name, desc, price, stock, reorder, vi in product_specs:
            products.append(Product.objects.create(
                sku=sku,
                name=name,
                description=desc,
                price=Decimal(price),
                stock_quantity=stock,
                reorder_level=reorder,
                vendor=vendors[vi],
            ))
        by_sku = {p.sku: p for p in products}

        # (customer_name, customer_email, vendor_index, [(sku, qty), ...], status)
        order_specs = [
            ('Jane Doe', 'jane@example.com', 0, [('TECH-001', 2), ('TECH-004', 1)], 'processed'),
            ('John Smith', 'john@example.com', 0, [('TECH-002', 1), ('GLOB-002', 1)], 'shipped'),
            ('Alice Brown', 'alice@example.com', 2, [('FRESH-001', 2), ('FRESH-003', 1)], 'shipped'),
            ('Bob Wilson', 'bob@example.com', 0, [('TECH-003', 1)], 'pending'),
            ('Carol Green', 'carol@example.com', 1, [('GLOB-001', 1)], 'cancelled'),
            ('David Lee', 'david@example.com', 0, [('TECH-001', 3)], 'processed'),
            ('Emma Davis', 'emma@example.com', 1, [('GLOB-002', 2)], 'shipped'),
            ('Frank Miller', 'frank@example.com', 2, [('FRESH-002', 1)], 'pending'),
        ]

        for customer_name, customer_email, vi, items, status in order_specs:
            order = Order.objects.create(
                vendor=vendors[vi],
                customer_name=customer_name,
                customer_email=customer_email,
            )
            for sku, qty in items:
                OrderItem.objects.create(
                    order=order,
                    product=by_sku[sku],
                    quantity=qty,
                    unit_price=by_sku[sku].price,
                )
            if status == 'shipped':
                order.transition_to('processed')
                order.transition_to('shipped')
            elif status == 'processed':
                order.transition_to('processed')
            elif status == 'cancelled':
                order.transition_to('cancelled')
