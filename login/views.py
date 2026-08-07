from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import reports
from .invoice_utils import generate_invoice_pdf
from .models import Invoice, Order, OrderItem, Product, StockAlert, StockMovement, Vendor
from .permissions import IsAnyRole, IsStaffOrReadOnly, IsStaffRole
from .serializers import (
    InvoiceSerializer,
    OrderItemSerializer,
    OrderSerializer,
    ProductSerializer,
    RegisterSerializer,
    StockAlertSerializer,
    StockMovementSerializer,
    UserSerializer,
    VendorSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class VendorListCreateView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        vendors = Vendor.objects.all()
        search = request.query_params.get('search')
        if search:
            vendors = vendors.filter(name__icontains=search)
        return Response(VendorSerializer(vendors, many=True).data)

    def post(self, request):
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorRetrieveUpdateDestroyView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)
        return Response(VendorSerializer(vendor).data)

    def put(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)
        serializer = VendorSerializer(vendor, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        vendor = get_object_or_404(Vendor, pk=pk)
        vendor.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductListCreateView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        products = Product.objects.select_related('vendor').all()
        search = request.query_params.get('search')
        if search:
            products = products.filter(
                name__icontains=search,
            )
        vendor_id = request.query_params.get('vendor')
        if vendor_id:
            products = products.filter(vendor_id=vendor_id)
        if request.query_params.get('low_stock') == 'true':
            products = products.filter(stock_quantity__lte=F('reorder_level'))
        if request.query_params.get('out_of_stock') == 'true':
            products = products.filter(stock_quantity=0)
        return Response(ProductSerializer(products, many=True).data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductRetrieveUpdateDestroyView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, pk):
        product = get_object_or_404(Product.objects.select_related('vendor'), pk=pk)
        return Response(ProductSerializer(product).data)

    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderListCreateView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request):
        orders = Order.objects.select_related('vendor').prefetch_related('items').all()
        status_filter = request.query_params.get('status')
        if status_filter:
            orders = orders.filter(status=status_filter)
        search = request.query_params.get('search')
        if search:
            orders = orders.filter(
                customer_name__icontains=search,
            )
        return Response(OrderSerializer(orders, many=True).data)

    def post(self, request):
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        items_data = request.data.get('items', [])
        if not items_data:
            return Response(
                {'items': ['An order must contain at least one item.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                order = serializer.save()
                for item_data in items_data:
                    item_data['order'] = order.id
                    item_serializer = OrderItemSerializer(data=item_data)
                    item_serializer.is_valid(raise_exception=True)
                    item_serializer.save()
                order.refresh_from_db()
        except (serializers.ValidationError, DjangoValidationError) as exc:
            return Response({'items': exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderRetrieveUpdateDestroyView(APIView):
    permission_classes = [IsStaffOrReadOnly]

    def get(self, request, pk):
        order = get_object_or_404(
            Order.objects.select_related('vendor').prefetch_related('items'),
            pk=pk,
        )
        return Response(OrderSerializer(order).data)

    def put(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = OrderSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(OrderSerializer(order).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderProcessView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            order.transition_to('processed')
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)


class OrderShipView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            order.transition_to('shipped')
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            order.cancel()
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)


class InvoiceListView(APIView):
    def get(self, request):
        invoices = Invoice.objects.select_related('order').all()
        return Response(InvoiceSerializer(invoices, many=True).data)


class InvoiceDownloadView(APIView):
    """Download invoice as a PDF file."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        pdf_buffer = generate_invoice_pdf(invoice)
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        )
        return response


class StockAlertListView(APIView):
    def get(self, request):
        alerts = StockAlert.objects.select_related('product').all()
        resolved = request.query_params.get('resolved')
        if resolved == 'true':
            alerts = alerts.filter(resolved=True)
        elif resolved == 'false':
            alerts = alerts.filter(resolved=False)
        return Response(StockAlertSerializer(alerts, many=True).data)


class StockAlertResolveView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, pk):
        alert = get_object_or_404(StockAlert, pk=pk)
        alert.resolved = True
        alert.save(update_fields=['resolved'])
        return Response(StockAlertSerializer(alert).data)


class StockMovementListView(APIView):
    def get(self, request, product_id=None):
        movements = StockMovement.objects.select_related('product').all()
        if product_id is not None:
            movements = movements.filter(product_id=product_id)
        movement_type = request.query_params.get('type')
        if movement_type:
            movements = movements.filter(movement_type=movement_type.upper())
        return Response(StockMovementSerializer(movements, many=True).data)


class ReportSummaryView(APIView):
    """Dashboard metrics for inventory and orders."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        return Response(reports.inventory_summary())


class TopProductsReportView(APIView):
    """Best-selling products ranked by units sold."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        return Response({'products': reports.top_products(limit=limit)})


class VendorReportView(APIView):
    """Per-vendor product, order, and revenue breakdown."""
    permission_classes = [IsAnyRole]

    def get(self, request):
        return Response({'vendors': reports.vendor_report()})
