import random

from django.utils import timezone
from rest_framework import serializers

from .models import Address, Notification, OTP, User


class SendOTPSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=15)

    def validate_mobile_number(self, value):
        digits_only = ''.join(filter(str.isdigit, value))
        if len(digits_only) < 10:
            raise serializers.ValidationError("Invalid mobile number.")
        return value

    def create_otp(self, mobile_number):
        OTP.objects.filter(mobile_number=mobile_number, is_used=False).update(is_used=True)
        otp_code = f"{random.randint(100000, 999999)}"
        otp = OTP.objects.create(mobile_number=mobile_number, otp=otp_code)
        print(f"\n{'='*40}")
        print(f"  MOCK OTP for {mobile_number}: {otp_code}")
        print(f"{'='*40}\n")
        return otp_code


class VerifyOTPSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        mobile_number = attrs['mobile_number']
        otp_code = attrs['otp']

        otp = OTP.objects.filter(
            mobile_number=mobile_number,
            otp=otp_code,
            is_used=False
        ).first()

        if not otp:
            raise serializers.ValidationError({"msg": "Invalid or expired OTP."})

        if otp.created_at < timezone.now() - timezone.timedelta(minutes=5):
            raise serializers.ValidationError({"msg": "OTP has expired. Please request a new one."})

        attrs['otp_obj'] = otp
        return attrs

    def get_or_create_user(self, validated_data):
        mobile_number = validated_data['mobile_number']
        otp_obj = validated_data['otp_obj']

        user, created = User.objects.get_or_create(
            mobile_number=mobile_number,
            defaults={'username': mobile_number, 'role': 'customer'}
        )

        otp_obj.is_used = True
        otp_obj.save()

        return user, created


class ApplyReferralSerializer(serializers.Serializer):
    referral_code = serializers.CharField(max_length=12)

    def validate_referral_code(self, value):
        try:
            referrer = User.objects.get(referral_code=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid referral code.")
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        if user.referred_by is not None:
            raise serializers.ValidationError({"msg": "You have already applied a referral code."})
        if user.referral_code == attrs['referral_code']:
            raise serializers.ValidationError({"msg": "You cannot refer yourself."})
        return attrs

    def apply(self, user):
        referrer = User.objects.get(referral_code=self.validated_data['referral_code'])
        user.referred_by = referrer
        user.save(update_fields=['referred_by'])


class MyReferralsSerializer(serializers.ModelSerializer):
    profile_completion = serializers.IntegerField(read_only=True)
    address_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'mobile_number', 'username', 'first_name', 'last_name',
            'email', 'role', 'profile_picture', 'date_of_birth', 'gender',
            'referral_code', 'profile_completion', 'address_count', 'date_joined',
        )

    def get_address_count(self, obj):
        return obj.addresses.count()


class ProfileSerializer(serializers.ModelSerializer):
    profile_completion = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'mobile_number', 'role', 'referral_code',
            'first_name', 'last_name', 'email',
            'profile_picture', 'date_of_birth', 'gender',
            'profile_completion',
        )
        read_only_fields = ('id', 'username', 'mobile_number', 'role', 'referral_code', 'profile_completion')

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ProfileCompletionSerializer(serializers.Serializer):
    profile_completion = serializers.IntegerField()
    filled_fields = serializers.ListField(child=serializers.CharField())
    missing_fields = serializers.ListField(child=serializers.CharField())


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            'id', 'label', 'house_number', 'street', 'area',
            'city', 'state', 'pincode', 'country',
            'latitude', 'longitude', 'is_default',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        user = self.context['request'].user
        if attrs.get('is_default') and not Address.objects.filter(user=user, is_default=True).exists():
            pass
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'title', 'message', 'notification_type', 'is_read', 'created_at')
        read_only_fields = ('id', 'created_at')
