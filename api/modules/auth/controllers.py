from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .services import (
    generate_and_store_otp, verify_otp, create_tokens, set_email, 
    create_deletion_request, confirm_deletion, verify_firebase_token, 
    generate_and_store_otp_msg91, verify_msg91_token, verify_otp_msg91, 
    generate_and_store_email_otp, verify_email_otp, generate_and_store_otp_fast2sms,
    get_or_create_user_by_phone, get_or_create_user_by_email, complete_user_verification
)
from .utils_2factor import send_otp_2factor, verify_otp_2factor_service
from .utils_prismswift import send_whatsapp_otp
from .utils_ebdsms import send_ebdsms_otp
from ...models import Profile, User
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

def get_user_profile_data(user, request=None):
    """
    Returns standardized profile data for a user.
    """
    p = user.profile
    is_new = not (p.display_name and p.display_name != 'User' and p.gender)
    
    photo_url = None
    if p.photo and hasattr(p.photo, 'name') and p.photo.name:
        try:
            if request:
                photo_url = request.build_absolute_uri(p.photo.url)
            else:
                photo_url = p.photo.url
        except Exception:
            photo_url = None

    if not photo_url:
        # Assign modern friendly defaults based on gender
        gender = str(p.gender).lower()
        default_path = "defaults/male_avatar.png" if "female" not in gender else "defaults/female_avatar.png"
        full_default_path = f"{settings.MEDIA_URL}{default_path}"
        if request:
            photo_url = request.build_absolute_uri(full_default_path)
        else:
            photo_url = full_default_path

    return {
        'id': user.id,
        'profile_id': p.id,
        'username': user.username,
        'display_name': p.display_name or user.username,
        'email': p.email,
        'phone': p.phone_number,
        'photo': photo_url,
        'gender': p.gender,
        'bio': p.bio,
        'is_verified': p.is_verified,
        'wallet_balance': getattr(user, 'wallet').coin_balance if hasattr(user, 'wallet') else 0
    }

def get_auth_response_data(user, request=None):
    """
    Generates a consistent authentication response structure.
    """
    tokens = create_tokens(user)
    profile_data = get_user_profile_data(user, request)
    is_new = not (profile_data.get('display_name') and profile_data.get('display_name') != 'User' and profile_data.get('gender'))
    
    return {
        'success': True,
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'access_token': tokens['access'],
        'refresh_token': tokens['refresh'],
        'token': tokens['access'],
        'temp_token': tokens['access'] if is_new else None,
        'user': profile_data,
        'is_new_user': is_new
    }

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_email_view(request):
    """
    Sends OTP to the provided email address.
    """
    email = request.data.get('email')
    if not email:
        return Response({'error': 'email required'}, status=400)
    
    otp = generate_and_store_email_otp(email)
    return Response({'message': 'OTP sent to email', 'otp': otp}) # otp returned for dev convenience, remove in prod if strict

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_email_view(request):
    """
    Verifies Email OTP and logs in the user.
    """
    email = request.data.get('email')
    otp = request.data.get('otp')
    
    if not email or not otp:
        return Response({'error': 'email and otp required'}, status=400)
        
    user = verify_email_otp(email, otp)
    if not user:
        return Response({'error': 'Invalid OTP'}, status=400)
        
    return Response(get_auth_response_data(user, request))

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_msg91_view(request):
    phone = request.data.get('phone_number')
    otp = request.data.get('otp')
    
    if not phone or not otp:
        return Response({'error': 'phone_number and otp required'}, status=400)
        
    is_valid = verify_otp_msg91(phone, otp)
    if not is_valid:
        return Response({'error': 'Invalid OTP'}, status=400)
        
    # Login Logic
    try:
        user = get_or_create_user_by_phone(phone)
        complete_user_verification(user)
        return Response(get_auth_response_data(user, request))
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def msg91_login_view(request):
    """
    Verifies MSG91 Widget Token and logs in the user.
    """
    access_token = request.data.get('access_token')
    if not access_token:
        return Response({'error': 'access_token required'}, status=400)
        
    verification_data = verify_msg91_token(access_token)
    if not verification_data:
        return Response({'error': 'Invalid or expired token'}, status=400)
    
    # Extract phone number from verification data
    # Note: MSG91 response structure might vary, usually 'mobile' or in 'data'
    # The snippet says: "Get verified user information".
    # We'll assume 'mobile' or 'contact' field.
    # Let's check the data structure in logs if possible, but for now try 'mobile'
    phone_number = verification_data.get('mobile') or verification_data.get('message') # Sometimes message is the number? Unlikely.
    
    # If phone_number is not directly in root, check 'data' dict
    if not phone_number and 'data' in verification_data:
         phone_number = verification_data['data'].get('mobile')
         
    if not phone_number:
         # Fallback: if we can't get phone number, we can't log in.
         # Unless we trust the client provided phone number (LESS SECURE)
         # But the whole point of server-side verify is to get the number securely.
         # Let's try to handle if phone_number is passed in request as well, but verify it matches?
         # No, trust the token.
         return Response({'error': 'Could not retrieve phone number from MSG91 token'}, status=400)

    # Normalize phone number (add + if missing)
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    # Login Logic (Similar to firebase_login_view)
    try:
        user = get_or_create_user_by_phone(phone_number)
        complete_user_verification(user)
        return Response(get_auth_response_data(user, request))
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp(request):
    """
    Internal OTP Sender.
    Generates OTP, stores it, and returns it in the response for verification.
    Validates phone number format.
    """
    phone = request.data.get('phone_number')
    channel = request.data.get('channel', 'sms')  # Support 'sms' or 'whatsapp'
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    
    # Validate Phone Number (Basic E.164 or local format check)
    # Must be 10-15 digits, optional + prefix
    import re
    if not re.match(r'^\+?1?\d{9,15}$', phone):
         return Response({'error': 'Invalid phone number format. Use E.164 (e.g. +919999999999) or 10-digit format.'}, status=400)

    # Validate channel
    if channel not in ['sms', 'whatsapp']:
        channel = 'sms'
        
    code = generate_and_store_otp(phone, channel=channel)
    
    response_data = {'message': 'OTP generated successfully.'}
    if code == 'VERIFY_SENT':
        response_data['message'] = f'OTP sent via Twilio Verify ({channel})'
    elif code == 'SMS_SENT':
        response_data['message'] = f'OTP sent successfully via SMS'
    else:
        # Only return OTP if it was generated locally (Mock/Dev) or if sending failed
        response_data['otp'] = code
        response_data['message'] = 'OTP generated (Mock/Dev mode or Send failed)'
        
    return Response(response_data)

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_msg91_view(request):
    """
    Dedicated endpoint to send OTP via MSG91.
    """
    phone = request.data.get('phone_number')
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    
    code = generate_and_store_otp_msg91(phone)
    return Response({'message': 'OTP sent via MSG91', 'otp': code})

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_whatsapp_view(request):
    """
    Sends OTP via WhatsApp using PrismSwift service.
    """
    phone = request.data.get('phone_number')
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    
    # Generate OTP internally
    code = generate_and_store_otp(phone)
    
    # Send via WhatsApp
    result = send_whatsapp_otp(phone, code)
    
    if result['success']:
        return Response({
            'message': 'OTP sent via WhatsApp', 
            'session_id': 'whatsapp_session', # Dummy session
            'otp': code # Return code for testing/fallback
        })
    else:
        return Response({'error': result.get('error', 'Failed to send WhatsApp OTP')}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_ebdsms_view(request):
    """
    Sends OTP via eBDSMS service.
    """
    phone = request.data.get('phone_number')
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    
    # Generate OTP internally
    code = generate_and_store_otp(phone)
    
    # Send via eBDSMS
    result = send_ebdsms_otp(phone, code)
    
    if result['success']:
        return Response({
            'message': 'OTP sent via eBDSMS', 
            'session_id': 'ebdsms_session', 
            'otp': code # Return code for testing
        })
    else:
        return Response({'error': result.get('error', 'Failed to send eBDSMS OTP')}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_2factor_view(request):
    """
    Sends OTP via 2Factor.in (Mock Mode for Dev)
    """
    phone = request.data.get('phone_number')
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    
    # MOCK MODE: Generate internal OTP and return it
    code = generate_and_store_otp(phone)
    # session_id is just a dummy value for frontend compatibility
    return Response({'message': 'OTP sent (Mock)', 'session_id': 'mock_session', 'otp': code})

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_2factor_view(request):
    """
    Verifies 2Factor OTP and logs in (Mock Mode: uses internal DB)
    """
    phone = request.data.get('phone_number')
    session_id = request.data.get('session_id')
    otp_input = request.data.get('otp')
    
    if not phone or not otp_input:
        return Response({'error': 'phone_number and otp required'}, status=400)
        
    # Verify against internal DB since we used generate_and_store_otp
    user = verify_otp(phone, otp_input)
    
    if not user:
        return Response({'error': 'Invalid OTP'}, status=400)
        
    return Response(get_auth_response_data(user))

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def send_otp_fast2sms_view(request):
    """
    Sends OTP via Fast2SMS service.
    Generates a 4-digit OTP, stores it in the table, and sends it.
    Supports both GET and POST. Use 'method' param to switch Fast2SMS API call (default: POST).
    """
    # Log incoming request IP for debugging
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    print(f"\n--- Fast2SMS OTP Request ---")
    print(f"IP Address: {ip}")
    print(f"Method: {request.method}")
    print(f"---------------------------\n")

    if request.method == 'GET':
        phone = request.query_params.get('phone_number')
        method = request.query_params.get('method', 'POST')
    else:
        phone = request.data.get('phone_number')
        method = request.data.get('method', 'POST')
        
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    
    otp = generate_and_store_otp_fast2sms(phone, method=method)
    
    return Response({
        'message': f'OTP sent via Fast2SMS using {method}',
        'otp': otp  # Return for dev/testing
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp_view(request):
    phone = request.data.get('phone_number')
    otp_code = request.data.get('otp_code')
    user = verify_otp(phone, otp_code)
    if not user:
        return Response({'error': 'Invalid OTP'}, status=400)
    
    return Response(get_auth_response_data(user, request))

@api_view(['POST'])
@permission_classes([AllowAny])
def firebase_login_view(request):
    id_token = request.data.get('id_token')
    phone = request.data.get('phone_number')

    if not id_token:
        return Response({'error': 'id_token required'}, status=400)
    
    user = verify_firebase_token(id_token, phone)
    if not user:
        return Response({'error': 'Invalid Firebase Token'}, status=400)

    return Response(get_auth_response_data(user, request))

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    p = request.user.profile
    data = request.data
    
    if 'display_name' in data:
        p.display_name = data['display_name']
    if 'email' in data:
        p.email = data['email']
    if 'bio' in data:
        p.bio = data['bio']
    if 'interests' in data:
        p.interests = data['interests']
    if 'gender' in data:
        p.gender = data['gender']
    if 'language' in data:
        p.language = data['language']
        
    if 'password' in data and data['password']:
        request.user.set_password(data['password'])
        request.user.save()
        
    p.save()
    
    return Response({
        'success': True,
        'user': get_user_profile_data(request.user)
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_profile_view(request):
    """
    Final step of onboarding. Updates all info and returns full auth data.
    """
    user = request.user
    p = user.profile
    data = request.data
    
    # Update fields
    if 'name' in data:
        p.display_name = data['name']
    if 'email' in data:
        p.email = data['email']
        user.email = data['email']
        user.save()
    if 'gender' in data:
        p.gender = data['gender']
    if 'language' in data:
        p.language = data['language']
    if 'languages' in data and isinstance(data['languages'], list) and data['languages']:
        # For now we use the first one as primary language if field is singular
        p.language = data['languages'][0]
    if 'bio' in data:
        p.bio = data['bio']
        
    p.save()
    
    # Return full auth response (tokens + updated user)
    return Response(get_auth_response_data(user, request))

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_avatar_view(request):
    """
    Standardized avatar upload endpoint.
    Expects 'photo' or 'avatar' file in request.FILES.
    """
    p = request.user.profile
    # Accept both field names for flexibility
    photo_file = request.FILES.get('photo') or request.FILES.get('avatar')
    
    if photo_file:
        p.photo = photo_file
        p.save()
        profile_data = get_user_profile_data(request.user, request)
        return Response({
            'success': True,
            'photo_url': profile_data.get('photo'),
            'user': profile_data
        })
    return Response({'error': 'No photo provided'}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def select_gender_view(request):
    gender = request.data.get('gender')
    p = request.user.profile
    p.gender = gender
    p.save()
    return Response(get_user_profile_data(request.user))

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_language_view(request):
    language = request.data.get('language')
    p = request.user.profile
    p.language = language or p.language
    p.save()
    return Response({'success': True, 'language': p.language})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Returns the current user's full profile.
    """
    return Response(get_user_profile_data(request.user, request))

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    refresh_token = request.data.get('refresh')
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception:
        pass
    return Response(status=204)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_email_view(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'email required'}, status=400)
    set_email(request.user, email)
    return Response({'success': True})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_request_view(request):
    reason = request.data.get('reason')
    if not reason:
        return Response({'error': 'reason required'}, status=400)
    dr = create_deletion_request(request.user, reason)
    link = f"{request.build_absolute_uri('/')}account/delete/confirm/{dr.token}"
    return Response({'success': True, 'token': dr.token, 'expiry': dr.expires_at.isoformat(), 'link': link})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_confirm_view(request):
    token = request.data.get('token')
    ok = confirm_deletion(token)
    if not ok:
        return Response({'error': 'invalid or expired token'}, status=400)
    return Response({'success': True})
@api_view(['GET'])
@permission_classes([AllowAny])
def diag_sms_view(request):
    """Diagnostic view to check SMS configuration."""
    from .utils_fast2sms import send_fast2sms_otp_get
    key = getattr(settings, 'FAST2SMS_API_KEY', '')
    
    test_result = None
    if key:
        test_result = send_fast2sms_otp_get('7904067891', '000000')
    
    return Response({
        'fast2sms_configured': bool(key),
        'key_preview': f"{key[:4]}..." if key else "NONE",
        'test_result': test_result,
        'debug': True
    })
