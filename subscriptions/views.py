import razorpay
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Address, Notification, User
from orders.models import DeliverySlot

from .models import Payment, ReferralDiscountTier, Subscription
from .serializers import (
    CancelSubscriptionSerializer,
    CreatePaymentSerializer,
    CreateSubscriptionSerializer,
    PaymentSerializer,
    ReferralDiscountTierSerializer,
    SubscriptionSerializer,
)


class ReferralDiscountTierListView(APIView):
    serializer_class = ReferralDiscountTierSerializer

    @extend_schema(summary='List all referral discount tiers')
    def get(self, request):
        tiers = ReferralDiscountTier.objects.all()
        serializer = ReferralDiscountTierSerializer(tiers, many=True)
        return Response({
            "msg": "Discount tiers fetched successfully.",
            "tiers": serializer.data,
        }, status=200)


class ReferralDiscountTierDetailView(APIView):
    serializer_class = ReferralDiscountTierSerializer

    @extend_schema(
        summary='Create a referral discount tier (Admin only)',
        examples=[OpenApiExample('Example', value={'min_referrals': 2, 'discount_per_unit': 2.00})],
    )
    def post(self, request):
        if not request.user.is_staff:
            return Response({"msg": "You do not have permission to perform this action."}, status=403)
        serializer = ReferralDiscountTierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "msg": "Discount tier created successfully.",
            "tier": serializer.data,
        }, status=201)

    @extend_schema(summary='Update a referral discount tier (Admin only)')
    def put(self, request, pk):
        if not request.user.is_staff:
            return Response({"msg": "You do not have permission to perform this action."}, status=403)
        try:
            tier = ReferralDiscountTier.objects.get(pk=pk)
        except ReferralDiscountTier.DoesNotExist:
            return Response({"msg": "Discount tier not found."}, status=404)
        serializer = ReferralDiscountTierSerializer(tier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "msg": "Discount tier updated successfully.",
            "tier": serializer.data,
        }, status=200)

    @extend_schema(summary='Delete a referral discount tier (Admin only)')
    def delete(self, request, pk):
        if not request.user.is_staff:
            return Response({"msg": "You do not have permission to perform this action."}, status=403)
        try:
            tier = ReferralDiscountTier.objects.get(pk=pk)
        except ReferralDiscountTier.DoesNotExist:
            return Response({"msg": "Discount tier not found."}, status=404)
        tier.delete()
        return Response({"msg": "Discount tier deleted successfully."}, status=200)


class CreateSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateSubscriptionSerializer

    @extend_schema(
        summary='Create a subscription with Razorpay payment',
        description='Create a new 30-day subscription. Returns Razorpay order for payment.',
        examples=[OpenApiExample('Example', value={
            'product_id': 1,
            'address_id': 1,
            'delivery_slot_id': 1,
            'quantity': 2.0,
            'start_date': '2026-07-20',
        })],
    )
    def post(self, request):
        serializer = CreateSubscriptionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subscription = Subscription.objects.create(
            user=request.user,
            product=data['product'],
            address=data['address'],
            delivery_slot=data.get('delivery_slot'),
            quantity=data['quantity'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            price_per_unit=data['price_per_unit'],
            discount_per_unit=data['discount_per_unit'],
            final_price_per_unit=data['final_price_per_unit'],
            total_amount=data['total_amount'],
        )

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        razorpay_order = client.order.create({
            'amount': int(subscription.total_amount * 100),
            'currency': 'INR',
            'receipt': f'sub_{subscription.id}',
        })

        subscription.razorpay_order_id = razorpay_order['id']
        subscription.save(update_fields=['razorpay_order_id'])

        Notification.objects.create(
            user=request.user,
            title='Subscription Created',
            message=f'Your subscription for {subscription.product.name} has been created. Please complete the payment.',
            notification_type='subscription',
        )

        return Response({
            "msg": "Subscription created successfully. Complete payment to activate.",
            "subscription": SubscriptionSerializer(subscription).data,
            "razorpay_order": {
                'order_id': razorpay_order['id'],
                'amount': razorpay_order['amount'],
                'currency': razorpay_order['currency'],
                'key': settings.RAZORPAY_KEY_ID,
            },
        }, status=201)


class VerifySubscriptionPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Verify subscription Razorpay payment',
        examples=[OpenApiExample('Example', value={
            'razorpay_order_id': 'order_xxx',
            'razorpay_payment_id': 'pay_xxx',
            'razorpay_signature': 'xxx',
        })],
    )
    def post(self, request):
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return Response({"msg": "All payment fields are required."}, status=400)

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
            })
        except Exception:
            return Response({"msg": "Payment verification failed."}, status=400)

        try:
            subscription = Subscription.objects.get(razorpay_order_id=razorpay_order_id, user=request.user)
        except Subscription.DoesNotExist:
            return Response({"msg": "Subscription not found."}, status=404)

        subscription.razorpay_payment_id = razorpay_payment_id
        subscription.razorpay_signature = razorpay_signature
        subscription.save(update_fields=['razorpay_payment_id', 'razorpay_signature'])

        Payment.objects.create(
            user=request.user,
            subscription=subscription,
            payment_for='subscription',
            amount=subscription.total_amount,
            payment_method='razorpay',
            payment_status='completed',
            razorpay_payment_id=razorpay_payment_id,
        )

        Notification.objects.create(
            user=request.user,
            title='Payment Successful',
            message=f'Payment of ₹{subscription.total_amount} for {subscription.product.name} subscription confirmed.',
            notification_type='payment',
        )

        return Response({
            "msg": "Payment verified and subscription activated.",
            "subscription": SubscriptionSerializer(subscription).data,
        }, status=200)


class MySubscriptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='List my subscriptions')
    def get(self, request):
        subscriptions = Subscription.objects.filter(user=request.user)
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response({
            "msg": "Subscriptions fetched successfully.",
            "subscriptions": serializer.data,
        }, status=200)


class SubscriptionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Get subscription details')
    def get(self, request, pk):
        try:
            subscription = Subscription.objects.get(pk=pk, user=request.user)
        except Subscription.DoesNotExist:
            return Response({"msg": "Subscription not found."}, status=404)
        serializer = SubscriptionSerializer(subscription)
        return Response({
            "msg": "Subscription fetched successfully.",
            "subscription": serializer.data,
        }, status=200)


class CancelSubscriptionPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Preview prorated cancellation',
        description='See how much you will owe if you cancel now.',
    )
    def get(self, request, pk):
        try:
            subscription = Subscription.objects.get(pk=pk, user=request.user)
        except Subscription.DoesNotExist:
            return Response({"msg": "Subscription not found."}, status=404)
        if subscription.status != 'active':
            return Response({"msg": "Only active subscriptions can be cancelled."}, status=400)

        return Response({
            "msg": "Cancel preview",
            "start_date": str(subscription.start_date),
            "end_date": str(subscription.end_date),
            "cancelled_on": str(timezone.now().date()),
            "total_days": subscription.total_days,
            "days_used": subscription.days_used,
            "days_remaining": subscription.days_remaining,
            "total_amount": str(subscription.total_amount),
            "amount_used": str(subscription.amount_used),
            "refund_amount": str(subscription.refund_amount),
        }, status=200)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cancel subscription with prorated billing',
        description='Cancel subscription mid-way. Only pays for days used.',
        examples=[OpenApiExample('Example', value={
            'payment_method': 'upi',
            'transaction_id': 'UPI123456',
        })],
    )
    def post(self, request, pk):
        try:
            subscription = Subscription.objects.get(pk=pk, user=request.user)
        except Subscription.DoesNotExist:
            return Response({"msg": "Subscription not found."}, status=404)
        if subscription.status != 'active':
            return Response({"msg": "Only active subscriptions can be cancelled."}, status=400)

        subscription.status = 'cancelled'
        subscription.cancelled_at = timezone.now()
        subscription.save(update_fields=['status', 'cancelled_at'])

        amount_used = subscription.amount_used

        if amount_used > 0:
            serializer = CancelSubscriptionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            Payment.objects.create(
                user=request.user,
                subscription=subscription,
                payment_for='subscription',
                amount=amount_used,
                payment_method=serializer.validated_data.get('payment_method', 'cash'),
                payment_status='completed',
                transaction_id=serializer.validated_data.get('transaction_id', ''),
                notes='Prorated payment on cancellation',
            )

        if subscription.refund_amount > 0:
            Payment.objects.create(
                user=request.user,
                subscription=subscription,
                payment_for='subscription',
                amount=subscription.refund_amount,
                payment_method='razorpay',
                payment_status='refunded',
                notes='Refund for unused subscription days',
            )

        Notification.objects.create(
            user=request.user,
            title='Subscription Cancelled',
            message=f'Your {subscription.product.name} subscription has been cancelled. Amount used: ₹{amount_used}, Refund: ₹{subscription.refund_amount}',
            notification_type='subscription',
        )

        return Response({
            "msg": "Subscription cancelled successfully.",
            "subscription": SubscriptionSerializer(subscription).data,
            "amount_used": str(amount_used),
            "refund_amount": str(subscription.refund_amount),
        }, status=200)


class AdminCreateSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Admin creates subscription for a user',
        description='Super admin can create a subscription on behalf of any user and record payment.',
        examples=[OpenApiExample('Example', value={
            'user_id': 1,
            'product_id': 1,
            'address_id': 1,
            'delivery_slot_id': 1,
            'quantity': 2.0,
            'start_date': '2026-07-20',
            'payment_method': 'cash',
            'mark_as_paid': True,
        })],
    )
    def post(self, request):
        if not request.user.is_staff:
            return Response({"msg": "You do not have permission to perform this action."}, status=403)

        user_id = request.data.get('user_id')
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"msg": "User not found."}, status=404)

        data = request.data.copy()
        data['user'] = user
        context = {'request': type('obj', (object,), {'user': user})()}

        serializer = CreateSubscriptionSerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        subscription = Subscription.objects.create(
            user=user,
            product=validated['product'],
            address=validated['address'],
            delivery_slot=validated.get('delivery_slot'),
            quantity=validated['quantity'],
            start_date=validated['start_date'],
            end_date=validated['end_date'],
            price_per_unit=validated['price_per_unit'],
            discount_per_unit=validated['discount_per_unit'],
            final_price_per_unit=validated['final_price_per_unit'],
            total_amount=validated['total_amount'],
        )

        mark_as_paid = request.data.get('mark_as_paid', False)
        if mark_as_paid:
            Payment.objects.create(
                user=user,
                subscription=subscription,
                payment_for='subscription',
                amount=subscription.total_amount,
                payment_method=request.data.get('payment_method', 'cash'),
                payment_status='completed',
                notes='Payment recorded by admin',
            )

        Notification.objects.create(
            user=user,
            title='Subscription Created',
            message=f'Admin created a subscription for {subscription.product.name}.',
            notification_type='subscription',
        )

        return Response({
            "msg": "Subscription created successfully by admin.",
            "subscription": SubscriptionSerializer(subscription).data,
        }, status=201)


class PaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='List my payment history')
    def get(self, request):
        payments = Payment.objects.filter(user=request.user)
        serializer = PaymentSerializer(payments, many=True)
        return Response({
            "msg": "Payment history fetched successfully.",
            "total": payments.count(),
            "total_paid": str(payments.filter(payment_status='completed').values_list('amount', flat=True).sum()),
            "payments": serializer.data,
        }, status=200)


class PaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Get payment details')
    def get(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk, user=request.user)
        except Payment.DoesNotExist:
            return Response({"msg": "Payment not found."}, status=404)
        serializer = PaymentSerializer(payment)
        return Response({
            "msg": "Payment fetched successfully.",
            "payment": serializer.data,
        }, status=200)
