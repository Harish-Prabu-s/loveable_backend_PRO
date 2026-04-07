import re
from django.contrib.auth.models import User
from .services import create_notification
from .push_service import send_push_notification, _get_user_tokens
from ..chat.services import get_or_create_room, send_message

def parse_mentions(text):
    """Extract usernames starting with @ from text."""
    if not text:
        return []
    # Find @ followed by alphanumeric and underscore, at least 3 chars
    return re.findall(r'@([a-zA-Z0-9_]{3,})', text)

def handle_mentions(text, actor, content_type, object_id, request=None, obj=None, explicit_mentions=None):
    """
    Process mentions in text and explicit mentions list:
    - Populates the 'mentions' M2M field if obj is provided
    - Creates Notifications for all mentioned users
    - Sends Push Notifications
    - Sends a chat message alert with a shareable link/object
    """
    usernames = parse_mentions(text)
    
    # Fetch explicit mention users
    explicit_users = []
    if explicit_mentions:
        explicit_users = list(User.objects.filter(id__in=explicit_mentions))

    if not usernames and not explicit_users:
        return

    # Filter out duplicates and actor's own username from parsed list
    usernames = list(set(usernames))
    if actor.username in usernames:
        usernames.remove(actor.username)

    # Combine parsed users with explicit users
    mentioned_users = list(User.objects.filter(username__in=usernames))
    
    # Merge using a set to avoid duplicates
    user_pool = {u.id: u for u in mentioned_users + explicit_users}
    if actor.id in user_pool:
        del user_pool[actor.id]
    
    final_users = list(user_pool.values())
    
    if not final_users:
        return

    # Update M2M field if object is provided (for Post, Reel, Story, Streak)
    if obj and hasattr(obj, 'mentions'):
        obj.mentions.set(final_users)

    profile = getattr(actor, 'profile', None)
    sender_name = profile.display_name if profile else actor.username

    content_label = content_type.replace('_', ' ')
    
    for target_user in final_users:
        # Determine metadata for advanced routing
        notif_metadata = {}
        if obj:
            notif_metadata['comment_id'] = getattr(obj, 'id', None)
            
        # 1. Database Notification
        notif_type = f"mention_{content_type}"
        create_notification(
            recipient=target_user,
            actor=actor,
            notification_type=notif_type,
            message=f"{sender_name} mentioned you in a {content_label}.",
            object_id=object_id,
            metadata=notif_metadata
        )

        # 2. Push Notification
        tokens = _get_user_tokens(target_user.id)
        if tokens:
            payload = {
                'type': 'mention',
                'mention_type': content_type,
                'actor_id': actor.id,
                'object_id': object_id,
            }
            if obj and hasattr(obj, 'id'):
                payload['comment_id'] = obj.id
                
            if content_type == 'post': payload['post_id'] = object_id
            elif content_type == 'reel': payload['reel_id'] = object_id
            elif content_type == 'story': payload['story_id'] = object_id
            elif content_type == 'streak': payload['streak_id'] = object_id
            elif content_type == 'post_comment' or content_type == 'comment': payload['post_id'] = object_id 
            elif content_type == 'reel_comment': payload['reel_id'] = object_id
            elif content_type == 'story_comment': payload['story_id'] = object_id
            elif content_type == 'streak_comment': payload['streak_id'] = object_id

            send_push_notification(
                tokens,
                title="You were mentioned!",
                body=f"{sender_name} mentioned you in a {content_label}.",
                data=payload
            )

        # 3. Chat Alert (Automatic Share)
        try:
            # Get or create room (using 'audio' as default for 1v1)
            room = get_or_create_room(actor, target_user.id, 'audio')
            
            # Map content_type to chat message type and content format
            share_type = 'text'
            share_content = f"I mentioned you in a {content_label}! Check it out."
            
            if content_type in ('post', 'post_comment', 'comment'):
                share_type = 'post_share'
                share_content = f"I mentioned you in a post! Check it out. [POST_SHARE:{object_id}:{getattr(obj, 'id', '')}]"
            elif content_type in ('reel', 'reel_comment'):
                share_type = 'reel_share'
                share_content = f"I mentioned you in a reel! Check it out. [REEL_SHARE:{object_id}:{getattr(obj, 'id', '')}]"
            elif content_type in ('story', 'story_comment'):
                share_type = 'story_share'
                share_content = f"I mentioned you in a story! Check it out. [STORY_SHARE:{object_id}:{getattr(obj, 'id', '')}]"
            elif content_type in ('streak', 'streak_comment'):
                share_type = 'streak_share'
                share_content = f"I mentioned you in a streak! Check it out. [STREAK_SHARE:{object_id}:{getattr(obj, 'id', '')}]"
            
            send_message(room.id, actor, share_content, share_type)
        except Exception as e:
            print(f"Error sending mention chat alert: {e}")
