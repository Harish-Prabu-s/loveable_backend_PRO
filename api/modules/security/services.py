import random
import string
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.contrib.auth.models import User
from ...models import UserSetting, EmailOTP

def get_user_settings(user: User):
    settings, created = UserSetting.objects.get_or_create(user=user)
    return settings

def set_app_lock_service(user: User, lock_type: str, value: str):
    settings = get_user_settings(user)
    settings.app_lock_type = lock_type
    settings.app_lock_value = value # In production, this should be HASHED if it's a password
    settings.save()
    return True, "App lock updated"

def verify_app_lock_service(user: User, value: str):
    settings = get_user_settings(user)
    if settings.app_lock_type == 'none':
        return True, "No lock set"
    if settings.app_lock_value == value:
        return True, "Verified"
    return False, "Invalid lock value"

def toggle_biometrics_service(user: User, enabled: bool):
    settings = get_user_settings(user)
    settings.biometrics_enabled = enabled
    settings.save()
    return True, f"Biometrics {'enabled' if enabled else 'disabled'}"

def toggle_face_unlock_service(user: User, enabled: bool):
    settings = get_user_settings(user)
    settings.face_unlock_enabled = enabled
    settings.save()
    return True, f"Face unlock {'enabled' if enabled else 'disabled'}"

def initiate_lock_reset_service(user: User):
    if not user.email:
        return False, "No email registered for this account. Please add an email first."
    
    code = ''.join(random.choices(string.digits, k=6))
    EmailOTP.objects.filter(email=user.email).update(is_used=True) # Invalidate old ones
    
    EmailOTP.objects.create(
        email=user.email,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=15)
    )
    
    try:
        send_mail(
            'App Lock Reset OTP',
            f'Your OTP to reset your app lock is: {code}. It expires in 15 minutes.',
            None,
            [user.email],
            fail_silently=False,
        )
        return True, "OTP sent to your email"
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False, "Failed to send email. Please try again later."

def verify_reset_otp_service(user: User, code: str):
    if not user.email:
        return False, "No email found"
    
    otp = EmailOTP.objects.filter(
        email=user.email, 
        code=code, 
        is_used=False, 
        expires_at__gt=timezone.now()
    ).first()
    
    if not otp:
        return False, "Invalid or expired OTP"
    
    otp.is_used = True
    otp.save()
    
    # Temporarily allow clearing or resetting
    settings = get_user_settings(user)
    settings.app_lock_type = 'none'
    settings.app_lock_value = ''
    settings.save()
    
    return True, "App lock cleared. You can now set a new one."
