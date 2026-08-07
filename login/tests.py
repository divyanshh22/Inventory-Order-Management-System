from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from login.models import (
    Invoice,
    Order,
    OrderItem,
    Product,
    StockAlert,
    StockMovement,
    Vendor,
)


class InventoryModelTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(
            name="Acme Tech",
            contact_person="Alex",
            email="acme@example.com",
        )
        self.product = Product.objects.create(
            sku="SKU-100",
            name="Laptop",
            price=Decimal("999.00"),
            stock_quantity=10,
            reorder_level=3,
            vendor=self.vendor,
        )

    def _create_order(self, quantity=2):
        order = Order.objects.create(
            vendor=self.vendor,
            customer_name="Jane Doe",
            customer_email="jane@example.com",
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=quantity,
            unit_price=self.product.price,
        )
        order.refresh_from_db()
        self.product.refresh_from_db()
        return order

    def test_full_flow_creates_invoice_tracks_stock_and_movement(self):
        order = self._create_order(quantity=2)

        self.assertEqual(order.total_amount, Decimal("1998.00"))
        self.assertTrue(order.order_number)
        self.assertEqual(self.product.stock_quantity, 8)

        invoice = Invoice.objects.get(order=order)
        self.assertEqual(invoice.total_amount, Decimal("1998.00"))
        self.assertTrue(invoice.invoice_number)

        movement = StockMovement.objects.get(
            product=self.product, movement_type=StockMovement.MovementType.STOCK_OUT
        )
        self.assertEqual(movement.quantity, 2)
        self.assertEqual(movement.previous_quantity, 10)
        self.assertEqual(movement.new_quantity, 8)
        self.assertEqual(movement.reference_id, order.order_number)

    def test_insufficient_stock_raises_and_does_not_deduct(self):
        order = Order.objects.create(
            vendor=self.vendor,
            customer_name="Jane Doe",
            customer_email="jane@example.com",
        )
        with self.assertRaises(ValidationError):
            OrderItem.objects.create(
                order=order,
                product=self.product,
                quantity=99,
                unit_price=self.product.price,
            )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertFalse(OrderItem.objects.filter(order=order).exists())
        order.delete()

    def test_order_cancel_restores_stock(self):
        order = self._create_order(quantity=2)
        self.assertEqual(self.product.stock_quantity, 8)

        order.cancel()
        self.product.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(order.stock_restored)

        restore = StockMovement.objects.filter(
            product=self.product,
            movement_type=StockMovement.MovementType.STOCK_IN,
        )
        self.assertEqual(restore.count(), 1)

    def test_cancel_is_idempotent(self):
        order = self._create_order(quantity=2)
        order.cancel()
        order.cancel()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_shipped_order_cannot_be_cancelled(self):
        order = self._create_order(quantity=2)
        order.transition_to('processed')
        order.transition_to('shipped')
        with self.assertRaises(ValidationError):
            order.cancel()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)

    def test_status_workflow_and_invalid_transitions(self):
        order = self._create_order(quantity=1)
        order.transition_to('processed')
        self.assertEqual(order.status, 'processed')
        order.transition_to('shipped')
        self.assertEqual(order.status, 'shipped')
        with self.assertRaises(ValidationError):
            order.transition_to('processed')

    def test_order_item_delete_restores_stock(self):
        order = self._create_order(quantity=2)
        self.assertEqual(self.product.stock_quantity, 8)

        item = order.items.first()
        item.delete()
        self.product.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(order.total_amount, Decimal("0.00"))

    def test_hard_delete_order_restores_stock(self):
        order = self._create_order(quantity=2)
        self.assertEqual(self.product.stock_quantity, 8)
        order.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_order_item_quantity_update_adjusts_stock(self):
        order = self._create_order(quantity=2)
        self.assertEqual(self.product.stock_quantity, 8)

        item = order.items.first()
        item.quantity = 4
        item.save()

        self.product.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 6)
        self.assertEqual(order.total_amount, Decimal("3996.00"))

    def test_low_stock_alert_created_and_notification_email(self):
        Product.objects.create(
            sku="SKU-200",
            name="Mouse",
            price=Decimal("25.00"),
            stock_quantity=2,
            reorder_level=3,
            vendor=self.vendor,
        )
        self.assertTrue(StockAlert.objects.filter(product__sku="SKU-200").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Mouse', mail.outbox[0].subject)

    def test_replenishing_stock_resolves_alert(self):
        product = Product.objects.create(
            sku="SKU-300",
            name="Keyboard",
            price=Decimal("50.00"),
            stock_quantity=1,
            reorder_level=5,
            vendor=self.vendor,
        )
        self.assertTrue(
            StockAlert.objects.filter(product=product, resolved=False).exists()
        )
        product.adjust_stock(10, notes="Restock")
        self.assertFalse(
            StockAlert.objects.filter(product=product, resolved=False).exists()
        )
        movement = StockMovement.objects.filter(
            product=product, movement_type=StockMovement.MovementType.STOCK_IN
        ).latest('created_at')
        self.assertEqual(movement.new_quantity, 11)

    def test_periodic_low_stock_scan(self):
        from login.tasks import check_all_low_stock

        Product.objects.create(
            sku="SKU-400",
            name="Monitor",
            price=Decimal("200.00"),
            stock_quantity=2,
            reorder_level=5,
            vendor=self.vendor,
        )
        result = check_all_low_stock.run()
        self.assertEqual(result['low_stock_count'], 1)


class InventoryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username='manager',
            email='manager@example.com',
            password='secret123',
        )
        self.staff_user.is_staff = True
        self.staff_user.save()
        managers, _ = Group.objects.get_or_create(name='Managers')
        self.staff_user.groups.add(managers)
        self.token = Token.objects.create(user=self.staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.vendor = Vendor.objects.create(
            name="Acme Tech",
            contact_person="Alex",
            email="acme@example.com",
        )
        self.product = Product.objects.create(
            sku="SKU-API-1",
            name="Tablet",
            price=Decimal("499.00"),
            stock_quantity=5,
            reorder_level=2,
            vendor=self.vendor,
        )

    def test_register_and_login(self):
        register = self.client.post(
            '/api/auth/register/',
            {
                'username': 'newuser',
                'email': 'new@example.com',
                'password': 'password123',
                'role': 'vendor',
            },
            format='json',
        )
        self.assertEqual(register.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', register.data)
        user = User.objects.get(username='newuser')
        self.assertTrue(user.groups.filter(name='Vendors').exists())

        login = self.client.post(
            '/api/auth/login/',
            {'username': 'newuser', 'password': 'password123'},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn('token', login.data)

    def test_unauthenticated_write_is_rejected(self):
        self.client.credentials()
        resp = self.client.post(
            '/api/vendors/',
            {
                'name': 'No Auth',
                'contact_person': 'Nobody',
                'email': 'no@example.com',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_read_endpoints_are_public(self):
        self.client.credentials()
        self.assertEqual(self.client.get('/api/vendors/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/products/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/orders/').status_code, status.HTTP_200_OK)

    def test_create_vendor_and_product(self):
        vendor_resp = self.client.post(
            '/api/vendors/',
            {
                'name': 'Beta Supplies',
                'contact_person': 'Bob',
                'email': 'beta@example.com',
            },
            format='json',
        )
        self.assertEqual(vendor_resp.status_code, status.HTTP_201_CREATED)

        product_resp = self.client.post(
            '/api/products/',
            {
                'sku': 'SKU-API-2',
                'name': 'Mouse',
                'price': '25.00',
                'stock_quantity': 10,
                'reorder_level': 2,
                'vendor_id': vendor_resp.data['id'],
            },
            format='json',
        )
        self.assertEqual(product_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(product_resp.data['vendor']['name'], 'Beta Supplies')

    def test_create_order_deducts_stock_and_returns_invoice(self):
        resp = self.client.post(
            '/api/orders/',
            {
                'customer_name': 'Jane Doe',
                'customer_email': 'jane@example.com',
                'vendor_id': self.vendor.id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 2,
                        'unit_price': '499.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data
        self.assertTrue(data['order_number'])
        self.assertEqual(Decimal(data['total_amount']), Decimal("998.00"))
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['invoice']['total_amount'], '998.00')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)

    def test_create_order_rejects_overselling(self):
        resp = self.client.post(
            '/api/orders/',
            {
                'customer_name': 'Jane Doe',
                'customer_email': 'jane@example.com',
                'vendor_id': self.vendor.id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 99,
                        'unit_price': '499.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertFalse(Order.objects.exists())

    def test_order_status_endpoints(self):
        order = self._create_order_via_api()

        process = self.client.post(f'/api/orders/{order.id}/process/')
        self.assertEqual(process.status_code, status.HTTP_200_OK)
        self.assertEqual(process.data['status'], 'processed')

        ship = self.client.post(f'/api/orders/{order.id}/ship/')
        self.assertEqual(ship.status_code, status.HTTP_200_OK)
        self.assertEqual(ship.data['status'], 'shipped')

        invalid = self.client.post(f'/api/orders/{order.id}/process/')
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_order_via_api_restores_stock(self):
        order = self._create_order_via_api()
        cancel = self.client.post(f'/api/orders/{order.id}/cancel/')
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data['status'], 'cancelled')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)

    def test_low_stock_and_movement_endpoints(self):
        self.client.post(
            '/api/orders/',
            {
                'customer_name': 'Jane Doe',
                'customer_email': 'jane@example.com',
                'vendor_id': self.vendor.id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 4,
                        'unit_price': '499.00',
                    }
                ],
            },
            format='json',
        )
        alerts = self.client.get('/api/alerts/')
        self.assertEqual(alerts.status_code, status.HTTP_200_OK)
        self.assertTrue(any(a['product'] is not None for a in alerts.data))

        movements = self.client.get('/api/stock-movements/')
        self.assertEqual(movements.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(movements.data), 1)
        self.assertEqual(movements.data[0]['movement_type'], 'OUT')

    def test_invoice_pdf_download(self):
        order = self._create_order_via_api()
        invoice = Invoice.objects.get(order=order)
        resp = self.client.get(f'/api/invoices/{invoice.id}/download/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def _create_order_via_api(self):
        resp = self.client.post(
            '/api/orders/',
            {
                'customer_name': 'Jane Doe',
                'customer_email': 'jane@example.com',
                'vendor_id': self.vendor.id,
                'items': [
                    {
                        'product_id': self.product.id,
                        'quantity': 1,
                        'unit_price': '499.00',
                    }
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        return Order.objects.get(order_number=resp.data['order_number'])

    def test_report_summary(self):
        self._create_order_via_api()
        self._create_order_via_api()

        resp = self.client.get('/api/reports/summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertEqual(data['products']['total'], 1)
        self.assertEqual(data['products']['total_stock_units'], 3)
        self.assertEqual(data['orders']['total'], 2)
        self.assertEqual(data['orders']['revenue'], Decimal("998.00"))

    def test_report_top_products_and_vendors(self):
        self._create_order_via_api()

        top = self.client.get('/api/reports/top-products/')
        self.assertEqual(top.status_code, status.HTTP_200_OK)
        self.assertEqual(top.data['products'][0]['product__sku'], 'SKU-API-1')
        self.assertEqual(top.data['products'][0]['units_sold'], 1)

        vendors = self.client.get('/api/reports/vendors/')
        self.assertEqual(vendors.status_code, status.HTTP_200_OK)
        self.assertEqual(vendors.data['vendors'][0]['name'], 'Acme Tech')
        self.assertEqual(vendors.data['vendors'][0]['revenue'], Decimal("499.00"))

    def test_reports_require_staff(self):
        user = User.objects.create_user(username='outsider', password='secret123')
        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        resp = client.get('/api/reports/summary/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class DashboardUITests(TestCase):
    PAGES = ['dashboard', 'products', 'vendors', 'orders', 'invoices', 'alerts', 'movements']

    def setUp(self):
        self.user = User.objects.create_user(username='admin', password='secret123', is_staff=True)

    def test_pages_redirect_anonymous_users_to_login(self):
        client = Client()
        for page in self.PAGES:
            resp = client.get(f'/{page}/')
            self.assertEqual(resp.status_code, 302, msg=page)
            self.assertIn('/admin/login/', resp.url, msg=page)

    def test_pages_render_for_staff(self):
        self.client.force_login(self.user)
        for page in self.PAGES:
            resp = self.client.get(f'/{page}/')
            self.assertEqual(resp.status_code, 200, msg=page)

    def test_root_redirects_to_dashboard(self):
        self.client.force_login(self.user)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/dashboard/')
