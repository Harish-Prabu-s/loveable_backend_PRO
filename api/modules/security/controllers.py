from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .services import (
    get_user_settings,
    set_app_lock_service,
    verify_app_lock_service,
    initiate_lock_reset_service,
    verify_reset_otp_service
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_app_lock(request):
    """Set the application lock type and value (PIN/Pattern/etc)"""
    lock_type = request.data.get('lock_type')
    value = request.data.get('value')
    if not lock_type or not value:
        return Response({'error': 'lock_type and value are required.'}, status=400)
    
    success, msg = set_app_lock_service(request.user, lock_type, value)
    return Response({'success': success, 'message': msg})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_app_lock(request):
    """Verify the provided lock value against stored settings"""
    value = request.data.get('value')
    if not value:
        return Response({'error': 'value is required.'}, status=400)
    
    success, msg = verify_app_lock_service(request.user, value)
    if success:
        return Response({'success': True, 'message': msg})
    return Response({'success': False, 'message': msg}, status=401)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_security_settings(request):
    """Bulk update security preferences and clear data if requested"""
    biometrics = request.data.get('biometrics_enabled')
    face = request.data.get('face_unlock_enabled')
    face_data = request.data.get('face_registration_data')
    fingerprint_data = request.data.get('fingerprint_registration_data')
    app_lock_type = request.data.get('app_lock_type')
    wipe = request.data.get('wipe', False)
    
    # Ensure get_user_settings is available from current namespace
    settings = get_user_settings(request.user)

    if wipe:
        settings.app_lock_type = 'none'
        settings.biometrics_enabled = False
        settings.face_unlock_enabled = False
        settings.face_registration_data = None
        settings.fingerprint_registration_data = None
        settings.app_lock_value = None
        settings.app_lock_pattern = None
        settings.save()
        return Response({'success': True, 'message': 'All security data cleared.'})
    
    if app_lock_type is not None:
        settings.app_lock_type = app_lock_type
    if biometrics is not None:
        settings.biometrics_enabled = biometrics
    if face is not None:
        settings.face_unlock_enabled = face
    if face_data is not None:
        settings.face_registration_data = face_data
    if fingerprint_data is not None:
        settings.fingerprint_registration_data = fingerprint_data
        
    settings.save()
    return Response({'success': True, 'message': 'Security settings updated.'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_lock_reset(request):
    """Trigger an email OTP for lock reset"""
    success, msg = initiate_lock_reset_service(request.user)
    if success:
        return Response({'success': True, 'message': msg})
    return Response({'success': False, 'message': msg}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_reset_otp(request):
    """Verify reset OTP and clear current lock if valid"""
    code = request.data.get('code')
    if not code:
        return Response({'error': 'OTP code is required.'}, status=400)
    
    success, msg = verify_reset_otp_service(request.user, code)
    if success:
        return Response({'success': True, 'message': msg})
    return Response({'success': False, 'message': msg}, status=400)
