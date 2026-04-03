import logging
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
from .push_service import send_push_notification, _get_user_tokens
import os

logger = logging.getLogger(__name__)

_firebase_initialized = False

def initialize_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True
    
    try:
        # Look for service account key in environment or default path
        cred_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        if not cred_path:
            # Check default path relative to BASE_DIR
            possible_path = os.path.join(settings.BASE_DIR, 'serviceAccountKey.json')
            if os.path.exists(possible_path):
                cred_path = possible_path
        
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized successfully.")
            return True
        else:
            logger.warning("Firebase service account key not found. FCM will not be available.")
    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")
    
    return False

def send_fcm_notification(user_id: int, title: str, body: str, data: dict = None):
    """
    Sends a direct FCM notification to a user.
    Falls back to Expo push notifications if Firebase is not initialized.
    """
    if not initialize_firebase():
        logger.info(f"Falling back to Expo for user {user_id}")
        tokens = _get_user_tokens(user_id)
        return send_push_notification(tokens, title, body, data)

    from api.models import Profile, PushToken
    
    # Get FCM tokens (stored in Profile.device_token if it's not an Expo token)
    # or if we have a separate field for FCM tokens eventually.
    # For now, we'll try to find any token that doesn't start with ExponentPushToken
    try:
        profile = Profile.objects.get(user_id=user_id)
        token = profile.device_token
        
        if not token or token.startswith('ExponentPushToken'):
            logger.info(f"No valid FCM token for user {user_id}, falling back to Expo")
            tokens = _get_user_tokens(user_id)
            return send_push_notification(tokens, title, body, data)

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
        )

        response = messaging.send(message)
        logger.info(f"Successfully sent FCM message: {response}")
        return {'sent': 1, 'errors': 0}
    except Exception as e:
        logger.error(f"Error sending FCM notification to user {user_id}: {e}")
        # Final fallback
        tokens = _get_user_tokens(user_id)
        return send_push_notification(tokens, title, body, data)

def send_action_notification(actor_name: str, recipient_id: int, action_type: str, object_id: str = None, extra_data: dict = None):
    """
    Generic function for all social notifications (like, comment, follow, etc.)
    """
    # Mapping of action types to messages
    MESSAGES = {
        'post_like': f"{actor_name} liked your post.",
        'post_comment': f"{actor_name} commented on your post.",
        'reel_like': f"{actor_name} liked your reel.",
        'reel_comment': f"{actor_name} commented on your reel.",
        'story_like': f"{actor_name} liked your story.",
        'friend_request': f"{actor_name} sent you a friend request.",
        'friend_request_accepted': f"{actor_name} accepted your friend request.",
        'chat_message': f"New message from {actor_name}",
        'incoming-call': f"{actor_name} is calling you...",
    }
    
    title = "New Notification"
    if action_type == 'incoming-call':
        title = "Incoming Call"
    elif 'like' in action_type:
        title = "New Like!"
    elif 'comment' in action_type:
        title = "New Comment!"
    elif 'friend' in action_type:
        title = "Friend Update"

    body = MESSAGES.get(action_type, f"New activity from {actor_name}")
    
    data = {
        'type': action_type,
        'actor_name': actor_name,
    }
    if object_id:
        data['object_id'] = str(object_id)
    if extra_data:
        data.update(extra_data)

    return send_fcm_notification(recipient_id, title, body, data)

def notify_followers(actor_name: str, actor_id: int, action_type: str, object_id: int):
    """
    Notifies all followers when a user uploads content.
    """
    from api.models import Follow
    follower_ids = Follow.objects.filter(following_id=actor_id).values_list('follower_id', flat=True)
    
    # Mapping of upload types
    TITLES = {
        'post_upload': 'New Post!',
        'reel_upload': 'New Reel!',
        'story_upload': 'New Story!',
    }
    BODIES = {
        'post_upload': f"{actor_name} just shared a new post.",
        'reel_upload': f"{actor_name} just uploaded a new reel.",
        'story_upload': f"{actor_name} added to their story.",
    }
    
    results = []
    for fid in follower_ids:
        res = send_push_notification(
            _get_user_tokens(fid),
            TITLES.get(action_type, 'New Update'),
            BODIES.get(action_type, f"{actor_name} uploaded new content."),
            {'type': action_type, 'actor_id': str(actor_id), 'object_id': str(object_id)}
        )
        results.append(res)
    return results

def notify_streak_update(user1_id: int, user2_id: int, count: int):
    """
    Special notification for streak milestones.
    """
    title = "🔥 Streak Update!"
    body = f"Your streak with your friend is now {count}! Keep it going!"
    
    data = {'type': 'streak_update', 'count': str(count)}
    
    send_fcm_notification(user1_id, title, body, data)
    send_fcm_notification(user2_id, title, body, data)

def send_call_notification(caller_name: str, callee_id: int, room_id: int, call_type: str):
    """
    Specialized function for incoming call notifications.
    Uses high priority and specific data payload for the mobile app to handle.
    """
    from api.models import UserSetting
    
    # Check if callee has offline calls enabled
    try:
        setting = UserSetting.objects.get(user_id=callee_id)
        if not setting.receive_offline_calls:
            logger.info(f"User {callee_id} has offline calls disabled.")
            return {'sent': 0, 'errors': 0, 'disabled': True}
    except UserSetting.DoesNotExist:
        pass

    return send_action_notification(
        caller_name, 
        callee_id, 
        'incoming-call', 
        object_id=str(room_id), 
        extra_data={'call_type': call_type}
    )
