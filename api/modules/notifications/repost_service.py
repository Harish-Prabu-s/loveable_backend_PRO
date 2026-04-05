from django.contrib.auth.models import User
from .push_service import send_push_notification, _get_user_tokens
from .services import create_notification
from ..chat.services import get_or_create_room, send_message

def notify_content_repost(reposter: User, original_owner: User, content_type: str, object_id: int):
    """
    Sends a push notification and an automated DM when a user's content is reposted.
    """
    if reposter == original_owner:
        return

    profile = getattr(reposter, 'profile', None)
    reposter_name = profile.display_name if profile else reposter.username
    
    title = "Content Reposted!"
    # User request: "reposted your story or reel or post or streak"
    body = f"{reposter_name} reposted your {content_type}!"
    
    # 1. Create In-App Notification
    create_notification(
        recipient=original_owner,
        actor=reposter,
        notification_type=f'{content_type}_repost',
        message=body,
        object_id=object_id
    )
    
    # 2. Send Push Notification
    tokens = _get_user_tokens(original_owner.id)
    if tokens:
        send_push_notification(
            tokens,
            title=title,
            body=body,
            data={'type': f'{content_type}_repost', 'id': object_id}
        )
        
    # 3. Send Automated DM
    try:
        room = get_or_create_room(reposter, original_owner.id, 'audio') # standard chat room
        send_message(
            room_id=room.id,
            sender=reposter,
            content=body,
            msg_type='text'
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send repost DM: {e}")
