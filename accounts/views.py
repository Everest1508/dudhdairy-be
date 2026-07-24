from drf_spectacular.utils import extend_schema, OpenApiExample
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from .models import Address, Notification, User
from .serializers import (
    AddressSerializer,
    ApplyReferralSerializer,
    MyReferralsSerializer,
    NotificationSerializer,
    ProfileCompletionSerializer,
    ProfileSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
)


class SendOTPView(APIView):
    serializer_class = SendOTPSerializer

    @extend_schema(
        summary='Send OTP to mobile number',
        description='Generates a 6-digit OTP and sends it to the provided mobile number. For now, the OTP is printed to the console (mock).',
        examples=[
            OpenApiExample('Example', value={'mobile_number': '9876543210'}),
        ],
        responses={200: {'msg': 'OTP sent successfully.'}},
    )
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile_number = serializer.validated_data['mobile_number']
        serializer.create_otp(mobile_number)
        return Response({"msg": "OTP sent successfully."}, status=200)


class VerifyOTPView(APIView):
    serializer_class = VerifyOTPSerializer

    @extend_schema(
        summary='Verify OTP and login',
        description='Verifies the OTP sent to the mobile number. If the user does not exist, a new account is automatically created with role "customer".',
        examples=[
            OpenApiExample('Example', value={'mobile_number': '9876543210', 'otp': '123456'}),
        ],
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, created = serializer.get_or_create_user(serializer.validated_data)

        refresh = RefreshToken.for_user(user)

        return Response({
            "msg": "Login successful." if not created else "Account created and login successful.",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "mobile_number": user.mobile_number,
                "role": user.role,
                "referral_code": user.referral_code,
                "username": user.username,
            }
        }, status=200)


class ApplyReferralView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ApplyReferralSerializer

    @extend_schema(
        summary='Apply a referral code',
        description='Apply another user\'s referral code. Can only be done once per account. You cannot refer yourself.',
        examples=[
            OpenApiExample('Example', value={'referral_code': 'AB12CD34'}),
        ],
    )
    def post(self, request):
        serializer = ApplyReferralSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.apply(request.user)
        return Response({"msg": "Referral code applied successfully."}, status=200)


class MyReferralsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='View my referrals',
        description='Get a list of all users who used your referral code to sign up.',
    )
    def get(self, request):
        referrals = User.objects.filter(referred_by=request.user).order_by('-date_joined')
        serializer = MyReferralsSerializer(referrals, many=True)
        return Response({
            "msg": "Referrals fetched successfully.",
            "total_referrals": referrals.count(),
            "referrals": serializer.data,
        }, status=200)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileSerializer

    @extend_schema(
        summary='Get my profile',
        description='Retrieve the authenticated user\'s profile information including profile completion percentage.',
    )
    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response({
            "msg": "Profile fetched successfully.",
            "profile": serializer.data,
        }, status=200)

    @extend_schema(
        summary='Update my profile',
        description='Update the authenticated user\'s profile information. Only provided fields will be updated.',
    )
    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "msg": "Profile updated successfully.",
            "profile": serializer.data,
        }, status=200)


class ProfileCompletionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Check profile completion',
        description='Returns the profile completion percentage along with filled and missing fields.',
    )
    def get(self, request):
        user = request.user
        all_fields = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'profile_picture': user.profile_picture,
            'date_of_birth': user.date_of_birth,
            'has_address': user.addresses.exists(),
        }
        filled = [field for field, value in all_fields.items() if value]
        missing = [field for field, value in all_fields.items() if not value]
        return Response({
            "msg": "Profile completion fetched successfully.",
            "profile_completion": user.profile_completion,
            "filled_fields": filled,
            "missing_fields": missing,
        }, status=200)


class AddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    @extend_schema(
        summary='List all addresses',
        description='Get all addresses for the authenticated user.',
    )
    def get(self, request):
        addresses = Address.objects.filter(user=request.user)
        serializer = AddressSerializer(addresses, many=True)
        return Response({
            "msg": "Addresses fetched successfully.",
            "addresses": serializer.data,
        }, status=200)

    @extend_schema(
        summary='Add a new address',
        description='Create a new address for the authenticated user.',
        examples=[
            OpenApiExample('Example', value={
                'label': 'home',
                'house_number': 'Flat 101, Sunshine Apartments',
                'street': 'MG Road',
                'area': 'Near City Mall',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'pincode': '400001',
                'country': 'India',
                'latitude': 19.0760,
                'longitude': 72.8777,
                'is_default': True,
            }),
        ],
    )
    def post(self, request):
        serializer = AddressSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "msg": "Address added successfully.",
            "address": serializer.data,
        }, status=201)


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AddressSerializer

    def get_object(self):
        address_id = self.kwargs.get('pk')
        try:
            return Address.objects.get(id=address_id, user=self.request.user)
        except Address.DoesNotExist:
            return None

    @extend_schema(
        summary='Get a single address',
        description='Retrieve a specific address by ID.',
    )
    def get(self, request, pk):
        address = self.get_object()
        if not address:
            return Response({"msg": "Address not found."}, status=404)
        serializer = AddressSerializer(address)
        return Response({
            "msg": "Address fetched successfully.",
            "address": serializer.data,
        }, status=200)

    @extend_schema(
        summary='Update an address',
        description='Update a specific address by ID.',
    )
    def put(self, request, pk):
        address = self.get_object()
        if not address:
            return Response({"msg": "Address not found."}, status=404)
        serializer = AddressSerializer(address, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "msg": "Address updated successfully.",
            "address": serializer.data,
        }, status=200)

    @extend_schema(
        summary='Delete an address',
        description='Delete a specific address by ID.',
    )
    def delete(self, request, pk):
        address = self.get_object()
        if not address:
            return Response({"msg": "Address not found."}, status=404)
        address.delete()
        return Response({"msg": "Address deleted successfully."}, status=200)


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='List my notifications',
        description='Get all notifications for the authenticated user.',
    )
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            "msg": "Notifications fetched successfully.",
            "total": notifications.count(),
            "unread_count": notifications.filter(is_read=False).count(),
            "notifications": serializer.data,
        }, status=200)


class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Mark a notification as read',
        description='Mark a specific notification as read.',
    )
    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({"msg": "Notification not found."}, status=404)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({"msg": "Notification marked as read."}, status=200)


class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Mark all notifications as read',
        description='Mark all unread notifications as read.',
    )
    def post(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({
            "msg": f"{updated} notification(s) marked as read.",
        }, status=200)
