from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import (
    get_notifications, mark_notifications_read, get_unread_count,
    send_follow_request, respond_to_follow_request,
    notify_screenshot,
)
from ...models import Notification, FollowRequest, PushToken
from django.contrib.auth.models import User



# ─── Notifications ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    """GET /notifications/ — list all notifications with optional ?unread=true"""
    unread_only = request.query_params.get('unread') == 'true'
    notifications = get_notifications(request.user, unread_only)
    data = []
    for n in notifications:
        actor_profile = getattr(n.actor, 'profile', None)
        request_status = None
        if n.notification_type == 'follow_request' and n.object_id:
            try:
                request_status = FollowRequest.objects.get(id=n.object_id).status
            except FollowRequest.DoesNotExist:
                pass
        elif n.notification_type == 'friend_request' and n.object_id:
            from ...models import FriendRequest
            try:
                request_status = FriendRequest.objects.get(id=n.object_id).status
            except FriendRequest.DoesNotExist:
                pass
        elif n.notification_type == 'game_invite' and n.object_id:
            from ...models import GameRoom
            try:
                request_status = GameRoom.objects.get(id=n.object_id).status
            except GameRoom.DoesNotExist:
                pass
        
        data.append({
            'id': n.id,
            'type': n.notification_type,
            'message': n.message,
            'is_read': n.is_read,
            'object_id': n.object_id,
            'metadata': n.metadata,
            'request_status': request_status,
            'created_at': n.created_at,
            'actor': {
                'id': n.actor.id if n.actor else None,
                'display_name': getattr(actor_profile, 'display_name', '') if actor_profile else '',
                'photo': request.build_absolute_uri(actor_profile.photo.url) if actor_profile and actor_profile.photo else None,
            } if n.actor else None,
        })
    return Response({'results': data, 'unread_count': get_unread_count(request.user)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request):
    """POST /notifications/read/ — mark notifications as read. Body: {ids: [1,2,3]} or empty for all."""
    ids = request.data.get('ids', None)
    mark_notifications_read(request.user, ids)
    return Response({'status': 'ok', 'unread_count': get_unread_count(request.user)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count_view(request):
    """GET /notifications/unread-count/ — returns the unread count only."""
    return Response({'unread_count': get_unread_count(request.user)})


# ─── Follow Requests ─────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_follow_request_view(request, user_id: int):
    """POST /notifications/follow-request/<user_id>/ — send follow request."""
    try:
        to_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)
    if to_user == request.user:
        return Response({'error': 'Cannot follow yourself'}, status=400)
    req = send_follow_request(request.user, to_user)
    return Response({'status': req.status, 'id': req.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_follow_request_view(request, request_id: int):
    """POST /notifications/follow-request/<request_id>/respond/ — accept or reject."""
    action = request.data.get('action')  # 'accept' or 'reject'
    if action not in ('accept', 'reject'):
        return Response({'error': 'action must be "accept" or "reject"'}, status=400)
    req, error = respond_to_follow_request(request_id, request.user, action)
    if error:
        return Response({'error': error}, status=404)
    return Response({'status': req.status, 'id': req.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_pending_follow_requests(request):
    """GET /notifications/follow-requests/ — incoming pending follow requests."""
    requests = FollowRequest.objects.filter(to_user=request.user, status='pending').select_related('from_user')
    data = []
    for fr in requests:
        actor_profile = getattr(fr.from_user, 'profile', None)
        data.append({
            'id': fr.id,
            'from_user': {
                'id': fr.from_user.id,
                'display_name': getattr(actor_profile, 'display_name', '') if actor_profile else '',
                'photo': request.build_absolute_uri(actor_profile.photo.url) if actor_profile and actor_profile.photo else None,
            },
            'created_at': fr.created_at,
        })
    return Response({'results': data})


# ─── Push Tokens ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_push_token(request):
    """POST /notifications/push-token/register/ — store or update Expo push token."""
    expo_token = request.data.get('expo_token', '').strip()
    device = request.data.get('device', '').strip()

    if not expo_token:
        return Response({'error': 'Token is required'}, status=400)

    # Legacy store (one token record per user)
    PushToken.objects.update_or_create(
        user=request.user,
        defaults={
            'expo_token': expo_token,
            'device': device
        },
    )
    
    # Store in Profile as requested
    profile = request.user.profile
    profile.device_token = expo_token
    profile.save()

    return Response({'status': 'registered'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def screenshot_notification_view(request):
    owner_id = request.data.get('owner_id')
    content_type = request.data.get('content_type') # 'story' or 'streak'
    content_id = request.data.get('content_id')
    
    if not owner_id or not content_type:
        return Response({'error': 'owner_id and content_type are required'}, status=400)
    
    notify_screenshot(request.user, int(owner_id), content_type, content_id)
    return Response({'status': 'notified'})
