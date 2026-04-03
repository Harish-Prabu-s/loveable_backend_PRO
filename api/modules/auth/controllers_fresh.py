from rest_framework.decorators import api_view, permission_classes, parser_classes
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
            pass
    elif p.photo and isinstance(p.photo, str):
        s = p.photo
        if request and '/media/' in s:
            idx = s.find('/media/')
            media_path = s[idx + len('/media/'):] if idx != -1 else s
            photo_url = request.build_absolute_uri(settings.MEDIA_URL + media_path)
        else:
            photo_url = s

    return {
        'id': user.id,
        'phone_number': p.phone_number,
        'email': p.email,
        'gender': p.gender,
        'display_name': p.display_name,
        'bio': p.bio,
        'interests': p.interests,
        'photo': photo_url,
        'language': p.language,
        'is_verified': p.is_verified,
        'is_online': p.is_online,
        'is_superuser': user.is_superuser,
        'date_joined': p.date_joined.isoformat() if p.date_joined else None,
        'last_login': p.last_login.isoformat() if p.last_login else None,
        'is_new_user': is_new
    }

def get_auth_response_data(user, request=None):
    """
    Generates a consistent authentication response structure.
    """
    tokens = create_tokens(user)
    profile_data = get_user_profile_data(user, request)
    is_new = profile_data.pop('is_new_user', False)
    
    return {
        'access_token': tokens['access_token'],
        'refresh_token': tokens['refresh_token'],
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
    if code != 'VERIFY_SENT':
        # Only return OTP if it was generated locally (Mock/Dev)
        response_data['otp'] = code
    else:
        response_data['message'] = f'OTP sent via Twilio Verify ({channel})'
        
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
        
    p.save()
    
    return Response({
        'success': True,
        'user': get_user_profile_data(request.user)
    })

from rest_framework.parsers import MultiPartParser, FormParser

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_avatar_view(request):
    try:
        # Debugging: Log what's arriving
        print(f"--- Upload Avatar Debug ---")
        print(f"Content-Type: {request.content_type}")
        print(f"FILES keys: {list(request.FILES.keys())}")
        print(f"DATA keys: {list(request.data.keys())}")
        
        if 'photo' not in request.FILES:
            return Response({'error': 'No photo provided. Found keys: ' + str(list(request.FILES.keys()))}, status=400)
        
        photo = request.FILES['photo']
        p = request.user.profile
        
        # Use a clean, predictable filename — React Native sometimes sends names
        # like "{uuid}.jpg" (with curly braces) which cause media-serving 404s.
        import time, os
        ext = os.path.splitext(photo.name)[1].lower() or '.jpg'
        clean_name = f"{request.user.id}_{int(time.time())}{ext}"
        filename = f"avatars/{clean_name}"
        path = default_storage.save(filename, ContentFile(photo.read()))
        
        p.photo = path
        p.save()
        photo_url = request.build_absolute_uri(settings.MEDIA_URL + path)
        return Response({'success': True, 'photo_url': photo_url})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

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
    return Response(get_user_profile_data(request.user))

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
