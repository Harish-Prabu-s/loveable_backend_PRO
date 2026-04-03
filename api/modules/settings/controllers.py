from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...models import UserSetting


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_settings(request):
    """GET /settings/ — retrieve current user settings (or defaults)."""
    settings_obj, _ = UserSetting.objects.get_or_create(user=request.user)
    return Response({
        'theme': settings_obj.theme,
        'call_preference': settings_obj.call_preference,
        'app_lock_type': settings_obj.app_lock_type,
        'notifications_enabled': settings_obj.notifications_enabled,
        'face_registration_data': settings_obj.face_registration_data,
        'fingerprint_registration_data': settings_obj.fingerprint_registration_data,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_settings(request):
    """PATCH /settings/ — update user settings."""
    settings_obj, _ = UserSetting.objects.get_or_create(user=request.user)
    data = request.data

    ALLOWED_FIELDS = [
        'theme', 'call_preference', 'app_lock_type', 
        'notifications_enabled', 'face_registration_data', 
        'fingerprint_registration_data'
    ]
    for field in ALLOWED_FIELDS:
        if field in data:
            setattr(settings_obj, field, data[field])

    # Handle app lock — store securely if PIN or pattern provided
    if 'app_lock_value' in data:
        import hashlib
        raw = str(data['app_lock_value'])
        settings_obj.app_lock_value = hashlib.sha256(raw.encode()).hexdigest()

    settings_obj.save()
    return Response({
        'theme': settings_obj.theme,
        'call_preference': settings_obj.call_preference,
        'app_lock_type': settings_obj.app_lock_type,
        'notifications_enabled': settings_obj.notifications_enabled,
        'face_registration_data': settings_obj.face_registration_data,
        'fingerprint_registration_data': settings_obj.fingerprint_registration_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_lock(request):
    """POST /settings/verify-lock/ — verify PIN/Pattern for app lock."""
    settings_obj, _ = UserSetting.objects.get_or_create(user=request.user)
    raw = str(request.data.get('value', ''))
    import hashlib
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    if hashed == settings_obj.app_lock_value:
        return Response({'valid': True})
    return Response({'valid': False}, status=400)
