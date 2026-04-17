from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .controllers import send_otp, verify_otp_view, select_gender_view, set_language_view, me, logout_view, set_email_view, delete_request_view, delete_confirm_view, update_profile_view, upload_avatar_view, firebase_login_view, send_otp_msg91_view, msg91_login_view, verify_otp_msg91_view, send_otp_email_view, verify_otp_email_view, send_otp_2factor_view, verify_otp_2factor_view, send_otp_whatsapp_view, send_otp_ebdsms_view, send_otp_fast2sms_view, complete_profile_view

urlpatterns = [
    path('send-otp/', send_otp),
    path('send-otp-email/', send_otp_email_view),
    path('verify-otp-email/', verify_otp_email_view),
    path('send-otp-msg91/', send_otp_msg91_view),
    path('msg91-login/', msg91_login_view),
    path('verify-otp-msg91/', verify_otp_msg91_view),
    path('send-otp-whatsapp/', send_otp_whatsapp_view), # PrismSwift
    path('send-otp-ebdsms/', send_otp_ebdsms_view),     # eBDSMS
    path('send-otp-fast2sms/', send_otp_fast2sms_view), # Fast2SMS
    path('send-otp-2factor/', send_otp_2factor_view),
    path('verify-otp-2factor/', verify_otp_2factor_view),
    path('verify-otp/', verify_otp_view),
    path('firebase-login/', firebase_login_view),
    path('select-gender/', select_gender_view),
    path('set-language/', set_language_view),
    path('me/', me),
    path('logout/', logout_view),
    path('set-email/', set_email_view),
    path('refresh/', TokenRefreshView.as_view()),
    path('delete/request/', delete_request_view),
    path('delete/confirm/', delete_confirm_view),
    path('update-profile/', update_profile_view),
    path('complete-profile/', complete_profile_view),
    path('upload-avatar/', upload_avatar_view),
    path('diag-sms/', diag_sms_view),
]
