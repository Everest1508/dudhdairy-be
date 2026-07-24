from rest_framework import serializers

from accounts.models import DeliveryBoyProfile, User
from accounts.serializers import AddressSerializer
from orders.models import Order
from orders.serializers import OrderSerializer, DeliverySlotSerializer
from subscriptions.models import Subscription
from subscriptions.serializers import SubscriptionSerializer

from .models import DailyDelivery


class DeliveryBoyProfileSerializer(serializers.ModelSerializer):
    mobile_number = serializers.CharField(source='user.mobile_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = DeliveryBoyProfile
        fields = (
            'id', 'mobile_number', 'first_name', 'last_name',
            'vehicle_number', 'is_available', 'zone',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class CreateDeliveryBoySerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=15)
    first_name = serializers.CharField(max_length=150, required=False, default='')
    last_name = serializers.CharField(max_length=150, required=False, default='')
    vehicle_number = serializers.CharField(max_length=20, required=False, default='')
    zone = serializers.CharField(max_length=100, required=False, default='')

    def validate_mobile_number(self, value):
        if User.objects.filter(mobile_number=value).exists():
            raise serializers.ValidationError("A user with this mobile number already exists.")
        return value

    def create(self, validated_data):
        mobile_number = validated_data['mobile_number']
        user = User.objects.create_user(
            username=mobile_number,
            mobile_number=mobile_number,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role='delivery_boy',
        )
        profile = DeliveryBoyProfile.objects.create(
            user=user,
            vehicle_number=validated_data.get('vehicle_number', ''),
            zone=validated_data.get('zone', ''),
        )
        return user, profile


class DeliveryBoyListSerializer(serializers.ModelSerializer):
    mobile_number = serializers.CharField(source='user.mobile_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    is_available = serializers.BooleanField(source='delivery_profile.is_available', read_only=True)
    zone = serializers.CharField(source='delivery_profile.zone', read_only=True)
    vehicle_number = serializers.CharField(source='delivery_profile.vehicle_number', read_only=True)
    total_deliveries = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'mobile_number', 'first_name', 'last_name',
            'is_available', 'zone', 'vehicle_number', 'total_deliveries',
            'is_active', 'date_joined',
        )

    def get_total_deliveries(self, obj):
        from django.utils import timezone
        return DailyDelivery.objects.filter(
            delivery_boy=obj, status='delivered'
        ).count()


class AssignOrderSerializer(serializers.Serializer):
    delivery_boy_id = serializers.IntegerField()
    order_id = serializers.IntegerField()

    def validate_delivery_boy_id(self, value):
        try:
            user = User.objects.get(id=value, role='delivery_boy')
        except User.DoesNotExist:
            raise serializers.ValidationError("Delivery boy not found.")
        return value

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(id=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")
        return value


class AssignSubscriptionSerializer(serializers.Serializer):
    delivery_boy_id = serializers.IntegerField()
    subscription_id = serializers.IntegerField()

    def validate_delivery_boy_id(self, value):
        try:
            user = User.objects.get(id=value, role='delivery_boy')
        except User.DoesNotExist:
            raise serializers.ValidationError("Delivery boy not found.")
        return value

    def validate_subscription_id(self, value):
        try:
            subscription = Subscription.objects.get(id=value, status='active')
        except Subscription.DoesNotExist:
            raise serializers.ValidationError("Active subscription not found.")
        return value


class UpdateDeliveryStatusSerializer(serializers.Serializer):
    STATUS_CHOICES = (
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    )
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class DailyDeliverySerializer(serializers.ModelSerializer):
    subscription_detail = SubscriptionSerializer(source='subscription', read_only=True)
    address_detail = AddressSerializer(source='subscription.address', read_only=True)
    product_name = serializers.CharField(source='subscription.product.name', read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_mobile = serializers.CharField(source='subscription.user.mobile_number', read_only=True)
    delivery_slot_detail = DeliverySlotSerializer(source='subscription.delivery_slot', read_only=True)

    class Meta:
        model = DailyDelivery
        fields = (
            'id', 'subscription', 'subscription_detail', 'delivery_date',
            'status', 'delivered_at', 'notes',
            'product_name', 'address_detail', 'customer_name', 'customer_mobile',
            'delivery_slot_detail',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'delivered_at', 'created_at', 'updated_at')

    def get_customer_name(self, obj):
        user = obj.subscription.user
        return f"{user.first_name} {user.last_name}".strip() or user.mobile_number
