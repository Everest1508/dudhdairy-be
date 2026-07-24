from django.urls import path

from .views import (
    AddressDetailView,
    AddressListCreateView,
    ApplyReferralView,
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    MyReferralsView,
    NotificationListView,
    ProfileCompletionView,
    ProfileView,
    SendOTPView,
    VerifyOTPView,
)

app_name = 'accounts'

urlpatterns = [
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('apply-referral/', ApplyReferralView.as_view(), name='apply-referral'),
    path('my-referrals/', MyReferralsView.as_view(), name='my-referrals'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/completion/', ProfileCompletionView.as_view(), name='profile-completion'),
    path('addresses/', AddressListCreateView.as_view(), name='address-list-create'),
    path('addresses/<int:pk>/', AddressDetailView.as_view(), name='address-detail'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/read/', MarkNotificationReadView.as_view(), name='notification-read'),
    path('notifications/read-all/', MarkAllNotificationsReadView.as_view(), name='notification-read-all'),
]
