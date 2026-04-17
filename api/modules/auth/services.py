from datetime import timedelta
import random
import string
from typing import Optional
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from ...models import Profile, OTP, Wallet, DeletionRequest, EmailOTP
from django.conf import settings
from .avatar_utils import assign_default_avatar
from twilio.rest import Client
import logging
from .utils_fast2sms import send_fast2sms_otp, send_fast2sms_otp_get
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# ... existing code ...

def get_or_create_user_by_email(email: str) -> User:
    profile = Profile.objects.filter(email=email).first()
    if profile:
        # Ensure wallet exists even for existing users
        Wallet.objects.get_or_create(user=profile.user)
        return profile.user
        
    username = f"user_{email.replace('@', '_at_').replace('.', '_dot_')}"
    # Ensure username is unique and not too long
    if len(username) > 150:
        username = username[:150]
        
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.set_unusable_password()
        user.save()
        
    profile, _ = Profile.objects.get_or_create(
        user=user, 
        defaults={
            'email': email, 
            'is_verified': False, 
            'phone_number': f"temp_{username}"
        }
    )
    if not profile.photo:
        assign_default_avatar(profile)
        
    Wallet.objects.get_or_create(user=user)
    return user

def generate_and_store_email_otp(email: str) -> str:
    otp = ''.join(random.choices(string.digits, k=6))
    EmailOTP.objects.create(
        email=email,
        code=otp,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=10),
        is_used=False
    )
    
    # Send Email
    try:
        # Use Django send_mail if configured, else try SMTP from user snippet (if credentials were present)
        # For now, we will use Django's send_mail which can be configured in settings.py
        
        subject = f"Vibely Login OTP - {otp}"
        message = f"""
        Dear User,
        
        Your OTP for Vibely login is: {otp}
        
        This OTP is valid for 10 minutes.
        
        Regards,
        Vibely Team
        """
        
        # HTML Version from user snippet (adapted)
        html_message = f"""
            Dear <b>User</b>,<br><br>
            We received a request to login to Vibely.<br><br>
            Your One-Time Password (OTP) is: <b>{otp}</b><br><br>
            Please use this OTP to complete the login process.
            For security reasons, this OTP is valid only for 10 minutes.<br><br>
            Regards,<br>
            Vibely Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message=html_message
        )
        logger.info(f"✅ OTP email sent successfully to {email}")
        
    except Exception as e:
        logger.error(f"❌ Failed to send OTP email: {e}")
        # For Dev/Test if email fails (e.g. no internet or config), print to console
        print(f"\n{'='*50}\n EMAIL OTP for {email}: {otp}\n{'='*50}\n")
        
    return otp

def verify_email_otp(email: str, code: str):
    otp = EmailOTP.objects.filter(email=email, code=code, is_used=False, expires_at__gt=timezone.now()).first()
    if not otp:
        return None
    user = get_or_create_user_by_email(email)
    otp.is_used = True
    otp.save()
    
    return complete_user_verification(user)


# Initialize Firebase Admin
try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
except Exception as e:
    logger.warning(f"Firebase Admin init failed: {e}")

def create_tokens(user: User):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }

def complete_user_verification(user: User) -> User:
    """
    Marks a user as verified and updates their last login timestamp in the profile.
    """
    profile: Profile = getattr(user, 'profile')  # type: ignore[attr-defined]
    profile.is_verified = True
    profile.last_login = timezone.now()
    profile.save()
    return user

def get_or_create_user_by_phone(phone: str) -> User:
    """
    Standardized user creation/retrieval by phone number.
    Ensures Profile and Wallet always exist.
    """
    # Ensure phone is a string
    phone = str(phone)
    
    # First, if any profile already owns this phone, return that user
    existing_by_phone = Profile.objects.filter(phone_number=phone).first()
    if existing_by_phone:
        Wallet.objects.get_or_create(user=existing_by_phone.user)
        return existing_by_phone.user
    
    # Normalize phone for username (remove '+' for username consistency if preferred, 
    # but existing code uses user_... or +... in some places. Let's stick to user_phone)
    clean_phone = phone.replace('+', '')
    username = f"user_{clean_phone}"
    
    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.create_user(username=username, password=None)
        user.set_unusable_password()
        user.save()
        
    profile, created = Profile.objects.get_or_create(user=user, defaults={'phone_number': phone})
    if not created and profile.phone_number != phone:
        profile.phone_number = phone
        profile.save()
        
    if not profile.photo:
        assign_default_avatar(profile)
        
    Wallet.objects.get_or_create(user=user)
    return user

def generate_and_store_otp_msg91(phone_number):
    """
    Generates an OTP using MSG91 API.
    """
    url = "https://control.msg91.com/api/v5/otp"
    
    # Ensure phone number has country code (default to 91 if not present)
    if not phone_number.startswith('+'):
        if len(phone_number) == 10:
             phone_number = '91' + phone_number
    
    # Remove '+' for MSG91
    mobile = phone_number.replace('+', '')
    
    params = {
        'template_id': settings.MSG91_TEMPLATE_ID,
        'mobile': mobile,
        'authkey': settings.MSG91_AUTH_KEY
    }
    
    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        data = response.json()
        # Note: MSG91 handles OTP storage and verification, so we might just return success
        # But for consistency with our system, we might want to know the OTP? 
        # MSG91 doesn't return the OTP in the response usually.
        # So this function is mainly for "sending" via MSG91.
        return "OTP sent via MSG91"
    except Exception as e:
        print(f"Error sending OTP via MSG91: {e}")
        # Fallback or re-raise
        return "Failed to send OTP"

def verify_otp_msg91(phone_number, otp):
    """
    Verifies OTP using MSG91 API.
    """
    url = "https://control.msg91.com/api/v5/otp/verify"
    
    # Ensure phone number has country code
    if not phone_number.startswith('+'):
        if len(phone_number) == 10:
             phone_number = '91' + phone_number
    
    mobile = phone_number.replace('+', '')
    
    querystring = {
        "otp": otp,
        "mobile": mobile,
        "authkey": settings.MSG91_AUTH_KEY
    }
    
    try:
        response = requests.get(url, params=querystring)
        response.raise_for_status()
        data = response.json()
        
        if data.get('type') == 'success' or data.get('message') == 'OTP verified success':
            return True
        return False
    except Exception as e:
        print(f"Error verifying MSG91 OTP: {e}")
        return False

def verify_msg91_token(access_token):
    """
    Verifies the access token from MSG91 Widget.
    """
    url = "https://control.msg91.com/api/v5/widget/verifyAccessToken"
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    body = {
        "authkey": settings.MSG91_AUTH_KEY,
        "access-token": access_token
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        
        # Check if successful
        if data.get('type') == 'success' or data.get('message') == 'success' or 'mobile' in data:
             # The structure depends on MSG91 response. 
             # Usually contains 'mobile' or 'message'.
             # Let's assume it returns the mobile number or we can extract it.
             # Based on docs, it returns 'message': 'success' and data with mobile.
             return data
        else:
             return None
    except Exception as e:
        print(f"Error verifying MSG91 token: {e}")
        return None

def generate_and_store_otp_fast2sms(phone_number, method='POST'):
    """
    Generates a 4-digit random OTP and sends it via Fast2SMS.
    Also stores it in the OTP table.
    'method' can be 'POST' or 'GET'.
    """
    # User requested random OTP for variables_values (OTP)
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Store in database
    OTP.objects.create(
        phone_number=phone_number,
        code=otp,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=10),
        is_used=False
    )
    
    # Send via Fast2SMS using requested method
    if method.upper() == 'GET':
        result = send_fast2sms_otp_get(phone_number, otp)
    else:
        result = send_fast2sms_otp(phone_number, otp)
    
    if result.get('success'):
        logger.info(f"Fast2SMS OTP {otp} sent to {phone_number} via {method}")
        return otp
    else:
        logger.error(f"Failed to send Fast2SMS OTP ({method}): {result.get('error')}")
        # Return otp anyway so it can be used for debugging/fallback
        return otp

def generate_and_store_otp(phone: str, channel: str = 'sms', trace: list = None) -> str:
    def _trace(msg):
        if trace is not None: trace.append(msg)
        print(f"DIAG_TRACE: {msg}")

    _trace(f"Entering generate_and_store_otp for {phone} (channel: {channel})")
    fast2sms_key = getattr(settings, 'FAST2SMS_API_KEY', None)
    _trace(f"FAST2SMS_API_KEY configured: {bool(fast2sms_key)} (Preview: {str(fast2sms_key)[:4]}...)")

    # 1. Generate Local code first
    code = ''.join(random.choices(string.digits, k=6))
    
    # 2. Try Fast2SMS First
    if channel == 'sms' and fast2sms_key:
        try:
            from .utils_fast2sms import send_fast2sms_otp_get
            _trace(f"Attempting Fast2SMS (OTP Route) for {phone}")
            result = send_fast2sms_otp_get(phone, code)
            _trace(f"Fast2SMS Result: {result}")
            
            if result.get('success'):
                OTP.objects.create(
                    phone_number=phone, code=code,
                    created_at=timezone.now(),
                    expires_at=timezone.now() + timedelta(minutes=10),
                    is_used=False
                )
                _trace("Returning SMS_SENT signal")
                return "SMS_SENT"
            else:
                _trace(f"Fast2SMS reports failure: {result.get('error')}")
        except Exception as e:
            _trace(f"Fast2SMS Exception caught: {str(e)}")
            logger.error(f"Fast2SMS failed: {e}")

    # 3. Try Twilio Verify (as secondary option)
    try:
        sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        verify_sid = getattr(settings, 'TWILIO_VERIFY_SID', None)
        
        if sid and token and verify_sid and sid.startswith('AC'):
            print(f"DEBUG: Attempting Twilio Verify for {phone}")
            from twilio.rest import Client
            client = Client(sid, token)
            verification = client.verify.v2.services(verify_sid) \
                .verifications \
                .create(to=phone, channel=channel)
            
            logger.info(f"Twilio Verify sent to {phone}: {verification.sid}")
            return "VERIFY_SENT"
    except Exception as e:
        print(f"DEBUG: Twilio Exception: {e}")
        logger.error(f"Twilio Verify failed: {e}")

    # 4. Final Fallback: Store locally and print to console (Dev/Mock)
    print(f"DEBUG: Falling back to Local/Console OTP for {phone}")
    OTP.objects.create(
        phone_number=phone,
        code=code,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=10),
        is_used=False
    )
    
    print(f"--- OTP FALLBACK for {phone}: {code} ---")
    try:
        send_mail('Your OTP Code', f'Use this code to login: {code}', None, [f'{phone}@sms.local'])
    except:
        pass

    return code

def verify_otp(phone: str, code: str):
    # 1. Try Twilio Verify Check
    try:
        sid = settings.TWILIO_ACCOUNT_SID
        token = settings.TWILIO_AUTH_TOKEN
        verify_sid = settings.TWILIO_VERIFY_SID
        
        if sid and token and verify_sid and sid.startswith('AC'):
            client = Client(sid, token)
            verification_check = client.verify.v2.services(verify_sid) \
                .verification_checks \
                .create(to=phone, code=code)
            
            if verification_check.status == 'approved':
                user = get_or_create_user_by_phone(phone)
                return complete_user_verification(user)
                
    except Exception as e:
        logger.error(f"Twilio Verify check failed: {e}")
        # Continue to fallback
        
    # 2. Fallback: Local OTP Check
    otp = OTP.objects.filter(phone_number=phone, code=code, is_used=False, expires_at__gt=timezone.now()).first()
    if not otp:
        return None
    user = get_or_create_user_by_phone(phone)
    otp.is_used = True
    otp.save()
    return complete_user_verification(user)

def set_email(user: User, email: str):
    """
    Sets the email for both User and Profile models.
    """
    user.email = email
    user.save()
    
    profile: Profile = getattr(user, 'profile')  # type: ignore[attr-defined]
    profile.email = email
    profile.save()
    return True

def create_deletion_request(user: User, reason: str):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
    dr = DeletionRequest.objects.create(
        user=user,
        reason=reason,
        token=token,
        expires_at=timezone.now() + timedelta(days=2),
    )
    return dr

def confirm_deletion(token: str):
    dr = DeletionRequest.objects.filter(token=token, expires_at__gt=timezone.now(), is_confirmed=False).first()
    if not dr:
        return False
    user = dr.user
    dr.is_confirmed = True
    dr.save()
    user.delete()
    return True

def verify_firebase_token(id_token: str, provided_phone: Optional[str] = None) -> Optional[User]:
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        phone_number = decoded_token.get('phone_number')
        email = decoded_token.get('email')
        
        user = None
        if phone_number:
            user = get_or_create_user_by_phone(phone_number)
        elif email:
            user = get_or_create_user_by_email(email)
        elif provided_phone:
             user = get_or_create_user_by_phone(provided_phone)
        
        if not user:
            logger.error("Firebase token verified but no phone, email, or provided_phone found")
            return None

        return complete_user_verification(user)

    except Exception as e:
        logger.error(f"Firebase verification failed: {e}")
        # DEVELOPMENT FALLBACK ONLY
        if provided_phone:
             logger.warning(f"DEV MODE: Skipping Firebase verification for {provided_phone} due to error")
             user = get_or_create_user_by_phone(provided_phone)
             return complete_user_verification(user)
             
        return None
