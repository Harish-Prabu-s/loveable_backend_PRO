from django.utils import timezone
from ...models import Notification, FollowRequest, Follow, Profile, CloseFriend
from django.contrib.auth.models import User


def create_notification(recipient: User, actor: User, notification_type: str, message: str = '', object_id: int = None, metadata: dict = None):
    """Central function to create a notification for a user."""
    # Don't notify yourself
    if recipient == actor:
        return None
    notif = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        message=message,
        object_id=object_id,
        metadata=metadata,
    )
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()
    
    try:
        if channel_layer:
            actor_profile = getattr(actor, 'profile', None) if actor else None
            # Real-time WebSockets update (Notification Channel)
            async_to_sync(channel_layer.group_send)(
                f'notifications_{recipient.id}',
                {
                    'type': 'send_notification',
                    'content': {
                        'type': 'new_notification',
                        'data': {
                            'id': notif.id,
                            'notification_type': notif.notification_type,
                            'message': notif.message,
                            'object_id': notif.object_id,
                            'metadata': notif.metadata,
                            'is_read': notif.is_read,
                            'created_at': notif.created_at.isoformat(),
                            'actor': {
                                'id': actor.id,
                                'display_name': getattr(actor_profile, 'display_name', '') if actor_profile else '',
                            } if actor else None
                        }
                    }
                }
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send real-time notification: {e}")

    return notif


def send_follow_request(from_user: User, to_user: User):
    """Send a follow request and create a notification."""
    req, created = FollowRequest.objects.get_or_create(from_user=from_user, to_user=to_user)
    if created:
        actor_name = getattr(from_user.profile, 'display_name', from_user.username)
        create_notification(
            recipient=to_user,
            actor=from_user,
            notification_type='follow_request',
            message=f'{actor_name} wants to follow you',
            object_id=req.id,
        )
    return req


def respond_to_follow_request(request_id: int, responding_user: User, action: str):
    """Accept or reject an incoming follow request."""
    try:
        req = FollowRequest.objects.get(id=request_id, to_user=responding_user, status='pending')
    except FollowRequest.DoesNotExist:
        return None, 'Request not found'

    if action == 'accept':
        req.status = 'accepted'
        req.save()
        # Create the actual follow relationship
        Follow.objects.get_or_create(follower=req.from_user, following=req.to_user)
        actor_name = getattr(responding_user.profile, 'display_name', responding_user.username)
        create_notification(
            recipient=req.from_user,
            actor=responding_user,
            notification_type='follow_accepted',
            message=f'{actor_name} accepted your follow request',
        )
    elif action == 'reject':
        req.status = 'rejected'
        req.save()
    return req, None


def get_notifications(user: User, unread_only: bool = False):
    """Get notifications for a user, newest first."""
    qs = Notification.objects.filter(recipient=user).select_related('actor').order_by('-created_at')
    if unread_only:
        qs = qs.filter(is_read=False)
    return qs[:100]  # cap at 100


def mark_notifications_read(user: User, notification_ids: list = None):
    """Mark notifications as read. If no IDs, mark all."""
    qs = Notification.objects.filter(recipient=user, is_read=False)
    if notification_ids:
        qs = qs.filter(id__in=notification_ids)
    qs.update(is_read=True)


def get_unread_count(user: User) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()


def notify_close_friends_of_content(uploader: User, content_type: str, object_id: int):
    """
    Optimized: Notify users who have the uploader in their Close Friends list.
    Uses bulk creation and pre-fetched tokens to handle large follower counts.
    """
    from ..notifications.push_service import send_push_notification
    from ...models import PushToken
    
    # 1. Fetch all close friend relationships in one query
    close_friendships = CloseFriend.objects.filter(close_friend=uploader).select_related('user')
    if not close_friendships.exists():
        return

    uploader_profile = getattr(uploader, 'profile', None)
    sender_name = uploader_profile.display_name if uploader_profile else uploader.username
    message = f"🌟 {sender_name} just uploaded a new {content_type}!"
    
    # 2. Prepare Notification objects for bulk creation
    notif_objects = [
        Notification(
            recipient=cf.user,
            actor=uploader,
            notification_type=f'close_friend_{content_type}',
            message=message,
            object_id=object_id
        ) for cf in close_friendships
    ]
    Notification.objects.bulk_create(notif_objects)

    # 3. Bulk fetch tokens for all recipients to avoid N+1
    recipient_ids = [cf.user_id for cf in close_friendships]
    all_tokens = PushToken.objects.filter(user_id__in=recipient_ids)
    
    # Map users to their tokens
    token_map = {}
    for t in all_tokens:
        if t.user_id not in token_map:
            token_map[t.user_id] = []
        token_map[t.user_id].append(t.expo_token)
    
    # 4. Send push notifications using pre-fetched tokens
    # Note: real-time WebSocket updates are skipped here for mass notifications 
    # to maintain high performance for the uploader's request.
    for user_id in recipient_ids:
        user_tokens = token_map.get(user_id)
        if user_tokens:
            try:
                send_push_notification(
                    user_tokens,
                    title="🌟 Close Friend Update",
                    body=message,
                    data={'type': f'close_friend_{content_type}', 'object_id': object_id, 'user_id': uploader.id}
                )
            except Exception:
                pass # Don't block if one push fails

def notify_screenshot(actor, owner_id, content_type, content_id):
    """
    Notifies content owner that someone took a screenshot.
    """
    try:
        owner = User.objects.get(id=owner_id)
        if actor == owner:
            return
        
        message = f"📸 {actor.username} took a screenshot of your {content_type}!"
        create_notification(
            recipient=owner,
            actor=actor,
            notification_type='screenshot',
            message=message,
            object_id=content_id
        )
        
        # Push notification
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        tokens = _get_user_tokens(owner_id)
        if tokens:
            send_push_notification(
                tokens,
                title="📸 Screenshot Alert",
                body=message,
                data={'type': 'screenshot', 'content_type': content_type, 'content_id': content_id}
            )
    except User.DoesNotExist:
        pass
