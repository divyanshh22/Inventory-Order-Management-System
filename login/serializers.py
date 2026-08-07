from django.contrib.auth.models import Group, User
from rest_framework import serializers

from .models import (
    Invoice,
    Order,
    OrderItem,
    Product,
    StockAlert,
    StockMovement,
    Vendor,
)

ROLE_GROUPS = {
    'admin': 'Admins',
    'manager': 'Managers',
    'staff': 'Staff',
    'vendor': 'Vendors',
}


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'roles']

    def get_roles(self, obj):
        return [group.name for group in obj.groups.all()]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(
        choices=list(ROLE_GROUPS.keys()),
        default='staff',
    )

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        group, _ = Group.objects.get_or_create(name=ROLE_GROUPS[role])
        user.groups.add(group)
        if role == 'admin':
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        return user


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.all(),
        source='vendor',
        write_only=True,
    )

    class Meta:
        model = Product
        fields = ['id', 'sku', 'name', 'description', 'price', 'stock_quantity', 'reorder_level', 'vendor', 'vendor_id']


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True,
    )
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        write_only=True,
    )

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'product', 'product_id', 'quantity', 'unit_price']

    def validate(self, attrs):
        product = attrs.get('product')
        quantity = attrs.get('quantity')
        if (
            product is not None
            and quantity is not None
            and self.instance is None
            and product.stock_quantity < quantity
        ):
            raise serializers.ValidationError({
                'quantity': [
                    f'Insufficient stock for {product.name}: '
                    f'available {product.stock_quantity}, requested {quantity}.'
                ],
            })
        return attrs


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__'


class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockAlert
        fields = ['id', 'product', 'product_name', 'message', 'created_at', 'resolved']


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'product', 'product_name', 'movement_type',
            'reference_type', 'reference_id', 'quantity',
            'previous_quantity', 'new_quantity', 'notes', 'created_at',
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    vendor = VendorSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(
        queryset=Vendor.objects.all(),
        source='vendor',
        write_only=True,
    )
    invoice = InvoiceSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'vendor', 'vendor_id', 'customer_name', 'customer_email', 'status', 'total_amount', 'items', 'invoice']

    def create(self, validated_data):
        return Order.objects.create(**validated_data)
