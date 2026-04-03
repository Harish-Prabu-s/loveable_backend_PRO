import random
import string
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Profile, OTP, Wallet, CoinTransaction, DeletionRequest, UserSetting
from .serializers import WalletSerializer, CoinTransactionSerializer
from django.conf import settings
try:
    from twilio.rest import Client
except ImportError:
    Client = None

def create_tokens(user: User):
    refresh = RefreshToken.for_user(user)
    return {'access_token': str(refresh.access_token), 'refresh_token': str(refresh)}

def get_or_create_profile(phone: str) -> tuple[User, bool]:
    profile = Profile.objects.filter(phone_number=phone).first()
    if profile:
        return profile.user, False
    username = f"user_{phone}"
    user = User.objects.create_user(username=username, password=None)
    Profile.objects.create(user=user, phone_number=phone, is_verified=False)
    Wallet.objects.create(user=user)
    UserSetting.objects.create(user=user)
    return user, True

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Simple health check endpoint to verify connectivity and database status.
    """
    db_ok = False
    db_error = None
    try:
        from django.contrib.auth.models import User
        count = User.objects.count()
        db_ok = True
    except Exception as e:
        db_error = str(e)

    status_code = status.HTTP_200_OK if db_ok else status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return Response({
        'status': 'ok' if db_ok else 'error',
        'database': 'connected' if db_ok else 'failed',
        'db_error': db_error,
        'message': 'API is reachable',
        'ip': request.META.get('REMOTE_ADDR'),
        'timestamp': timezone.now().isoformat()
    }, status=status_code)

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    """
    Webhook for WhatsApp API
    """
    VERIFY_TOKEN = "my_verify_token"

    if request.method == 'GET':
        # Verification Step
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook Verified!")
            return Response(int(challenge), status=status.HTTP_200_OK)
        
        return Response(status=status.HTTP_403_FORBIDDEN)

    elif request.method == 'POST':
        # Receiving Messages
        print("Incoming WhatsApp message:", request.data)
        return Response(status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp(request):
    phone = request.data.get('phone_number')
    if not phone:
        return Response({'error': 'phone_number required'}, status=400)
    code = ''.join(random.choices(string.digits, k=6))
    OTP.objects.create(
        phone_number=phone,
        code=code,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=10),
        is_used=False
    )
    
    # Send via Twilio if configured
    sent_via_sms = False
    if Client and hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID:
        sid = settings.TWILIO_ACCOUNT_SID
        if sid.startswith('VA'):
             print("Twilio Configuration Error: TWILIO_ACCOUNT_SID appears to be a Verify Service SID (starts with VA). Please provide the Account SID (starts with AC) in TWILIO_ACCOUNT_SID.")
        elif sid.startswith('AC'):
            try:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                client.messages.create(
                    body=f'Your Vibely OTP is: {code}',
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=phone if phone.startswith('+') else f'+91{phone}' # Assume IN if no prefix
                )
                sent_via_sms = True
                print(f"OTP sent via Twilio SMS to {phone}")
            except Exception as e:
                print(f"Twilio SMS Error: {e}")
        else:
             print(f"Twilio Configuration Error: Invalid TWILIO_ACCOUNT_SID format: {sid}")
            
    # Fallback to email/console for dev
    if not sent_via_sms:
        print(f"OTP FALLBACK (Console): Your OTP for {phone} is {code}")

    send_mail(
        'Your OTP Code',
        f'Use this code to login: {code}',
        None,
        [f'{phone}@sms.local'],
    )
    return Response({'message': 'OTP sent', 'otp': code if not sent_via_sms else 'sent_via_sms'})

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    try:
        phone = request.data.get('phone_number')
        otp_code = request.data.get('otp_code')
        otp = OTP.objects.filter(phone_number=phone, code=otp_code, is_used=False, expires_at__gt=timezone.now()).first()
        if not otp:
            return Response({'error': 'Invalid OTP'}, status=400)
        
        user, created = get_or_create_profile(phone)
        otp.is_used = True
        otp.save()
        
        tokens = create_tokens(user)
        profile = user.profile
        profile.is_verified = True
        profile.last_login = timezone.now()
        profile.save()
        
        # Safe photo URL access
        photo_url = None
        if profile.photo and hasattr(profile.photo, 'name') and profile.photo.name:
            try:
                photo_url = profile.photo.url
            except Exception:
                pass

        # If it's an existing user but they haven't set their name, consider them "new" for onboarding
        is_new = created or not profile.display_name or profile.display_name == 'User'

        return Response({
            'success': True,
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'token': tokens['access_token'], # Essential for frontend fallback
            'temp_token': tokens['access_token'] if is_new else None, # For onboarding flow
            'user': {
                'id': user.id,
                'phone_number': profile.phone_number,
                'display_name': profile.display_name,
                'gender': profile.gender,
                'is_verified': profile.is_verified,
                'is_online': profile.is_online,
                'date_joined': profile.date_joined.isoformat(),
                'last_login': profile.last_login.isoformat() if profile.last_login else None,
                'photo': photo_url
            },
            'is_new_user': is_new,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': 'Internal Server Error', 'details': str(e)}, status=500)

@api_view(['POST'])
def select_gender(request):
    gender = request.data.get('gender')
    profile = request.user.profile
    profile.gender = gender
    profile.save()
    return Response({
        'id': request.user.id,
        'phone_number': profile.phone_number,
        'gender': profile.gender,
        'is_verified': profile.is_verified,
        'is_online': profile.is_online,
        'date_joined': profile.date_joined.isoformat(),
        'last_login': profile.last_login.isoformat() if profile.last_login else None,
    })

@api_view(['GET'])
def me(request):
    profile = request.user.profile
    return Response({
        'id': request.user.id,
        'phone_number': profile.phone_number,
        'gender': profile.gender,
        'is_verified': profile.is_verified,
        'is_online': profile.is_online,
        'date_joined': profile.date_joined.isoformat(),
        'last_login': profile.last_login.isoformat() if profile.last_login else None,
    })

@api_view(['POST'])
def logout_view(request):
    refresh_token = request.data.get('refresh')
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
    except Exception:
        pass
    return Response(status=204)

@api_view(['POST'])
def set_email(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'email required'}, status=400)
    request.user.email = email
    request.user.save()
    p = request.user.profile
    p.email = email
    p.save()
    return Response({'success': True})

@api_view(['GET'])
def wallet(request):
    w = request.user.wallet
    return Response(WalletSerializer(w).data)

@api_view(['GET'])
def wallet_transactions(request):
    w = request.user.wallet
    qs = w.transactions.order_by('-created_at')[:50]
    return Response({
        'count': qs.count(),
        'next': None,
        'previous': None,
        'results': CoinTransactionSerializer(qs, many=True).data
    })

@api_view(['POST'])
def delete_request(request):
    reason = request.data.get('reason')
    if not reason:
        return Response({'error': 'reason required'}, status=400)
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=48))
    dr = DeletionRequest.objects.create(
        user=request.user,
        reason=reason,
        token=token,
        expires_at=timezone.now() + timedelta(days=2),
    )
    link = f"{request.build_absolute_uri('/')}account/delete/confirm/{token}"
    send_mail(
        'Confirm Account Deletion',
        f'Click to confirm deletion (valid for 2 days): {link}',
        None,
        [request.user.email or 'user@example.com'],
    )
    return Response({'success': True})

@api_view(['POST'])
@permission_classes([AllowAny])
def delete_confirm(request):
    token = request.data.get('token')
    dr = DeletionRequest.objects.filter(token=token, expires_at__gt=timezone.now(), is_confirmed=False).first()
    if not dr:
        return Response({'error': 'invalid or expired token'}, status=400)
    user = dr.user
    dr.is_confirmed = True
    dr.save()
    user.delete()
    return Response({'success': True})
