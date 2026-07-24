import secrets
import string

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('delivery_boy', 'Delivery Boy'),
        ('admin', 'Admin'),
    )

    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )

    mobile_number = models.CharField(max_length=15, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    referral_code = models.CharField(max_length=12, unique=True, blank=True)
    referred_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='referrals'
    )

    email = models.EmailField(max_length=255, blank=True, default='')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_referral_code():
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not User.objects.filter(referral_code=code).exists():
                return code

    @property
    def profile_completion(self):
        fields = {
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'profile_picture': self.profile_picture,
            'date_of_birth': self.date_of_birth,
            'has_address': self.addresses.exists(),
        }
        filled = sum(1 for value in fields.values() if value)
        total = len(fields)
        return round((filled / total) * 100)

    def __str__(self):
        return f"{self.mobile_number} ({self.get_role_display()})"


class DeliveryBoyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_profile')
    vehicle_number = models.CharField(max_length=20, blank=True, default='')
    is_available = models.BooleanField(default=True)
    zone = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Delivery Boy Profile'
        verbose_name_plural = 'Delivery Boy Profiles'

    def __str__(self):
        return f"{self.user.mobile_number} - {self.zone or 'No Zone'}"


class Address(models.Model):
    LABEL_CHOICES = (
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=20, choices=LABEL_CHOICES, default='home')
    house_number = models.CharField(max_length=50)
    street = models.CharField(max_length=255)
    area = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=50, default='India')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label}: {self.house_number}, {self.street}, {self.city}"


class Notification(models.Model):
    TYPE_CHOICES = (
        ('subscription', 'Subscription'),
        ('payment', 'Payment'),
        ('referral', 'Referral'),
        ('general', 'General'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.mobile_number} - {self.title}"


class OTP(models.Model):
    mobile_number = models.CharField(max_length=15, db_index=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.mobile_number} - {self.otp}"
