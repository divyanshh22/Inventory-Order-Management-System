from django.contrib import admin

from .models import Invoice, Order, OrderItem, Product, StockAlert, StockMovement, Vendor


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'contact_person', 'email', 'phone')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'sku', 'name', 'vendor', 'price', 'stock_quantity',
        'reorder_level', 'is_low_stock',
    )
    list_filter = ('vendor', 'reorder_level')
    search_fields = ('sku', 'name', 'vendor__name')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(boolean=True, description='Low stock')
    def is_low_stock(self, obj):
        return obj.stock_quantity <= obj.reorder_level


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer_name', 'customer_email', 'status',
        'total_amount', 'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'customer_name', 'customer_email')
    inlines = [OrderItemInline]
    readonly_fields = ('order_number', 'total_amount', 'stock_restored')
    actions = ['mark_processed', 'mark_shipped', 'cancel_orders']

    @admin.action(description='Mark selected orders as processed')
    def mark_processed(self, request, queryset):
        for order in queryset:
            try:
                order.transition_to('processed')
            except Exception as exc:
                self.message_user(request, f'{order.order_number}: {exc}', level='error')
        self.message_user(request, f'Processed {queryset.count()} order(s).')

    @admin.action(description='Mark selected orders as shipped')
    def mark_shipped(self, request, queryset):
        for order in queryset:
            try:
                order.transition_to('shipped')
            except Exception as exc:
                self.message_user(request, f'{order.order_number}: {exc}', level='error')
        self.message_user(request, f'Shipped {queryset.count()} order(s).')

    @admin.action(description='Cancel selected orders (returns stock)')
    def cancel_orders(self, request, queryset):
        for order in queryset:
            try:
                order.cancel()
            except Exception as exc:
                self.message_user(request, f'{order.order_number}: {exc}', level='error')
        self.message_user(request, f'Cancelled {queryset.count()} order(s).')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'order', 'customer_name', 'customer_email',
        'total_amount', 'issued_at',
    )
    search_fields = ('invoice_number', 'order__order_number', 'customer_name')
    readonly_fields = ('invoice_number', 'issued_at')


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('product', 'message', 'created_at', 'resolved')
    list_filter = ('resolved', 'created_at')
    search_fields = ('product__name', 'product__sku')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'movement_type', 'reference_type', 'reference_id',
        'quantity', 'previous_quantity', 'new_quantity', 'created_at',
    )
    list_filter = ('movement_type', 'reference_type', 'created_at')
    search_fields = ('product__name', 'product__sku', 'reference_id', 'notes')
    readonly_fields = (
        'product', 'movement_type', 'reference_type', 'reference_id',
        'quantity', 'previous_quantity', 'new_quantity', 'notes', 'created_at',
    )
